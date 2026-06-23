"""Capture de la sortie audio (loopback) et enregistrement en mémoire.

S'appuie sur la bibliothèque `soundcard`, qui sait enregistrer la sortie d'un
périphérique (« loopback ») sous Windows (WASAPI) comme sous Linux (moniteurs
PulseAudio/PipeWire). C'est ce qui permet de capturer « la sortie audio de ton
choix » : ce que tu entends en réunion (Teams, Zoom, Meet, …).

`soundcard` est importé paresseusement pour offrir un message d'erreur clair si
la dépendance manque, et pour que ce module reste importable hors d'un poste
équipé d'une carte son.
"""

from __future__ import annotations

import threading
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np


class AudioError(RuntimeError):
    """Erreur liée à la capture audio (périphérique, pilote, dépendance)."""


@dataclass(frozen=True)
class AudioDevice:
    """Représentation légère d'un périphérique audio."""

    id: str
    name: str
    is_loopback: bool = False

    def __str__(self) -> str:  # affichage convivial dans l'IHM
        return self.name


def _sc():
    """Importe `soundcard` avec un message d'erreur explicite si absent."""
    try:
        import soundcard

        return soundcard
    except Exception as exc:  # pragma: no cover - dépend de l'environnement
        raise AudioError(
            "La bibliothèque « soundcard » est requise pour la capture audio "
            "(pip install soundcard)."
        ) from exc


def list_loopback_devices() -> list[AudioDevice]:
    """Liste les périphériques de sortie capturables (loopback)."""
    sc = _sc()
    devices: list[AudioDevice] = []
    for mic in sc.all_microphones(include_loopback=True):
        if getattr(mic, "isloopback", False):
            devices.append(AudioDevice(id=str(mic.id), name=mic.name, is_loopback=True))
    return devices


def list_input_devices() -> list[AudioDevice]:
    """Liste les périphériques d'entrée réels (microphones)."""
    sc = _sc()
    return [
        AudioDevice(id=str(mic.id), name=mic.name, is_loopback=False)
        for mic in sc.all_microphones(include_loopback=False)
    ]


def get_default_loopback_device() -> Optional[AudioDevice]:
    """Périphérique de loopback associé au haut-parleur par défaut, si possible."""
    sc = _sc()
    try:
        speaker = sc.default_speaker()
        mic = sc.get_microphone(speaker.id, include_loopback=True)
        return AudioDevice(id=str(mic.id), name=mic.name, is_loopback=True)
    except Exception:
        loopbacks = list_loopback_devices()
        return loopbacks[0] if loopbacks else None


class Recorder:
    """Enregistreur audio non bloquant (capture dans des threads dédiés).

    Capture la sortie choisie (loopback) et, en option, le microphone, puis
    restitue un signal mono ``float32`` à l'arrêt. Le mixage micro + sortie est
    « best effort » : les deux flux sont alignés sur leur longueur commune.
    """

    def __init__(
        self,
        output_device_id: Optional[str] = None,
        samplerate: int = 48_000,
        include_microphone: bool = False,
        mic_device_id: Optional[str] = None,
        block_seconds: float = 0.1,
    ) -> None:
        self.output_device_id = output_device_id
        self.samplerate = samplerate
        self.include_microphone = include_microphone
        self.mic_device_id = mic_device_id
        self.block_frames = max(1, int(samplerate * block_seconds))

        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._loopback_frames: list[np.ndarray] = []
        self._mic_frames: list[np.ndarray] = []
        self._error: Optional[Exception] = None
        self._recording = False
        #: Niveau (RMS, 0..1) de la dernière tranche capturée — pour un vumètre.
        self.level: float = 0.0

    # ------------------------------------------------------------- contrôle
    def start(self) -> None:
        """Démarre la capture en arrière-plan."""
        if self._recording:
            raise AudioError("Un enregistrement est déjà en cours.")
        sc = _sc()
        self._reset()

        loopback_mic = self._resolve_loopback(sc)
        self._threads.append(
            threading.Thread(
                target=self._capture,
                args=(loopback_mic, self._loopback_frames, True),
                daemon=True,
            )
        )

        if self.include_microphone:
            mic = self._resolve_microphone(sc)
            if mic is not None:
                self._threads.append(
                    threading.Thread(
                        target=self._capture,
                        args=(mic, self._mic_frames, False),
                        daemon=True,
                    )
                )

        self._recording = True
        for thread in self._threads:
            thread.start()

    def stop(self) -> tuple[np.ndarray, int]:
        """Arrête la capture et renvoie ``(signal_mono_float32, samplerate)``."""
        if not self._recording:
            raise AudioError("Aucun enregistrement n'est en cours.")
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=5.0)
        self._recording = False

        if self._error is not None:
            raise AudioError(
                f"Erreur pendant la capture audio : {self._error}"
            ) from self._error

        loopback = _concat_mono(self._loopback_frames)
        if self.include_microphone and self._mic_frames:
            mic = _concat_mono(self._mic_frames)
            audio = _mix(loopback, mic)
        else:
            audio = loopback

        if audio.size == 0:
            raise AudioError(
                "Aucune donnée audio n'a été capturée. Vérifie que du son était "
                "bien émis sur le périphérique sélectionné."
            )
        return audio, self.samplerate

    @property
    def is_recording(self) -> bool:
        return self._recording

    # --------------------------------------------------------------- privé
    def _reset(self) -> None:
        self._stop.clear()
        self._threads.clear()
        self._loopback_frames.clear()
        self._mic_frames.clear()
        self._error = None
        self.level = 0.0

    def _resolve_loopback(self, sc):
        if self.output_device_id:
            try:
                return sc.get_microphone(self.output_device_id, include_loopback=True)
            except Exception as exc:
                raise AudioError(
                    "Le périphérique de sortie sélectionné est introuvable. "
                    "Rafraîchis la liste des périphériques."
                ) from exc
        device = get_default_loopback_device()
        if device is None:
            raise AudioError(
                "Aucun périphérique de loopback détecté. Sélectionne manuellement "
                "la sortie à capturer."
            )
        return sc.get_microphone(device.id, include_loopback=True)

    def _resolve_microphone(self, sc):
        try:
            if self.mic_device_id:
                return sc.get_microphone(self.mic_device_id, include_loopback=False)
            return sc.default_microphone()
        except Exception:
            return None  # micro indisponible : on continue sans

    def _capture(self, mic, frames: list[np.ndarray], track_level: bool) -> None:
        try:
            with mic.recorder(samplerate=self.samplerate) as rec:
                while not self._stop.is_set():
                    data = rec.record(numframes=self.block_frames)
                    frames.append(data.copy())
                    if track_level and data.size:
                        self.level = float(np.sqrt(np.mean(np.square(data))))
        except Exception as exc:  # remonte l'erreur au thread principal
            self._error = exc
            self._stop.set()


# ----------------------------------------------------------------- helpers
def _concat_mono(frames: list[np.ndarray]) -> np.ndarray:
    """Concatène des tranches multi-canaux et les réduit en mono ``float32``."""
    if not frames:
        return np.zeros(0, dtype=np.float32)
    data = np.concatenate(frames, axis=0)
    if data.ndim == 2 and data.shape[1] > 1:
        data = data.mean(axis=1)
    return np.asarray(data, dtype=np.float32).reshape(-1)


def _mix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Mixe deux signaux mono en les tronquant à leur longueur commune."""
    n = min(a.shape[0], b.shape[0])
    if n == 0:
        return a if a.shape[0] else b
    mixed = a[:n] + b[:n]
    # Évite l'écrêtage : on borne dans [-1, 1].
    return np.clip(mixed, -1.0, 1.0).astype(np.float32)


def save_wav(path: Path, audio: np.ndarray, samplerate: int) -> Path:
    """Écrit un signal mono ``float32`` dans un fichier WAV 16 bits."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(audio, -1.0, 1.0)
    pcm16 = (clipped * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(samplerate)
        wav.writeframes(pcm16.tobytes())
    return path


__all__ = [
    "AudioError",
    "AudioDevice",
    "Recorder",
    "list_loopback_devices",
    "list_input_devices",
    "get_default_loopback_device",
    "save_wav",
]
