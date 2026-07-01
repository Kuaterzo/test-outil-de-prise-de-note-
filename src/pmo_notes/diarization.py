"""Identification des locuteurs (diarisation) — fonctionnalité optionnelle.

La diarisation répond à « qui a dit quoi », ce qui améliore nettement
l'attribution des actions aux bonnes personnes dans la synthèse.

Deux parties :

* une logique d'alignement *pure* (sans dépendance lourde), qui associe chaque
  segment de transcription au locuteur dont le tour de parole se recouvre le
  plus, puis met en forme une transcription étiquetée — testable unitairement ;
* un :class:`Diarizer` qui s'appuie sur `pyannote.audio` (dépendance optionnelle,
  nécessitant un jeton Hugging Face) pour détecter les tours de parole.

Le tout dégrade gracieusement : si `pyannote.audio` ou le jeton manquent, le
pipeline retombe sur une transcription simple (voir :mod:`pipeline`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .transcription import TranscriptSegment

ProgressCallback = Optional[Callable[[str], None]]


class DiarizationError(RuntimeError):
    """Erreur de diarisation (dépendance, jeton, modèle, fichier)."""


@dataclass
class SpeakerTurn:
    """Tour de parole détecté : un intervalle attribué à un locuteur."""

    start: float
    end: float
    speaker: str


@dataclass
class LabeledSegment:
    """Segment de transcription enrichi du locuteur estimé."""

    start: float
    end: float
    text: str
    speaker: str


# --------------------------------------------------------------- logique pure
def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    """Durée de recouvrement entre deux intervalles (0 si disjoints)."""
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def assign_speakers(
    segments: list[TranscriptSegment], turns: list[SpeakerTurn]
) -> list[LabeledSegment]:
    """Associe à chaque segment le locuteur dont le tour se recouvre le plus.

    Un segment sans recouvrement hérite du locuteur précédent (continuité de la
    conversation), ou « ? » s'il n'y en a pas encore.
    """
    labeled: list[LabeledSegment] = []
    last_speaker: Optional[str] = None
    for seg in segments:
        best_speaker: Optional[str] = None
        best_overlap = 0.0
        for turn in turns:
            ov = _overlap(seg.start, seg.end, turn.start, turn.end)
            if ov > best_overlap:
                best_overlap = ov
                best_speaker = turn.speaker
        speaker = best_speaker if best_speaker is not None else (last_speaker or "?")
        last_speaker = speaker
        labeled.append(LabeledSegment(seg.start, seg.end, seg.text, speaker))
    return labeled


def friendly_speaker_names(labeled: list[LabeledSegment]) -> dict[str, str]:
    """Mappe les libellés bruts (« SPEAKER_00 ») vers « Locuteur 1 », … dans
    l'ordre d'apparition."""
    mapping: dict[str, str] = {}
    counter = 0
    for seg in labeled:
        if seg.speaker == "?":
            continue
        if seg.speaker not in mapping:
            counter += 1
            mapping[seg.speaker] = f"Locuteur {counter}"
    mapping.setdefault("?", "Locuteur ?")
    return mapping


def format_labeled_transcript(labeled: list[LabeledSegment]) -> str:
    """Met en forme une transcription « Locuteur N : … » par prise de parole.

    Les segments consécutifs d'un même locuteur sont regroupés sur une ligne.
    """
    if not labeled:
        return ""
    names = friendly_speaker_names(labeled)
    lines: list[str] = []
    current: Optional[str] = None
    buffer: list[str] = []

    def flush() -> None:
        if current is not None and buffer:
            lines.append(f"{current} : {' '.join(buffer).strip()}")

    for seg in labeled:
        name = names.get(seg.speaker, seg.speaker)
        if name != current:
            flush()
            current = name
            buffer = [seg.text.strip()]
        else:
            buffer.append(seg.text.strip())
    flush()
    return "\n".join(lines).strip()


# --------------------------------------------------------------- pyannote
class Diarizer:
    """Détection des tours de parole via `pyannote.audio` (import paresseux)."""

    def __init__(
        self,
        model: str = "pyannote/speaker-diarization-3.1",
        hf_token: Optional[str] = None,
    ) -> None:
        self.model = model
        # Le jeton peut venir de la config ou de l'environnement.
        self.hf_token = (
            hf_token
            or os.environ.get("HUGGINGFACE_TOKEN")
            or os.environ.get("HF_TOKEN")
        )
        self._pipeline = None

    def load(self, progress: ProgressCallback = None) -> None:
        """Charge le pipeline de diarisation (téléchargé au 1er usage)."""
        if self._pipeline is not None:
            return
        if not self.hf_token:
            raise DiarizationError(
                "La diarisation nécessite un jeton Hugging Face. Définis la "
                "variable d'environnement HUGGINGFACE_TOKEN (ou renseigne "
                "« hf_token » dans la configuration), et accepte les conditions "
                f"du modèle « {self.model} » sur huggingface.co."
            )
        try:
            from pyannote.audio import Pipeline
        except ImportError as exc:  # pragma: no cover - dépendance optionnelle
            raise DiarizationError(
                "Le paquet « pyannote.audio » est requis pour la diarisation "
                "(pip install pyannote.audio)."
            ) from exc

        if progress:
            progress("Chargement du modèle de diarisation…")
        try:
            self._pipeline = Pipeline.from_pretrained(
                self.model, use_auth_token=self.hf_token
            )
        except Exception as exc:
            raise DiarizationError(
                f"Impossible de charger le modèle de diarisation « {self.model} » : {exc}"
            ) from exc

    def diarize(self, audio_path: Path, progress: ProgressCallback = None) -> list[SpeakerTurn]:
        """Renvoie les tours de parole détectés dans le fichier audio."""
        self.load(progress)
        if progress:
            progress("Identification des locuteurs…")
        try:
            annotation = self._pipeline(str(audio_path))
        except Exception as exc:
            raise DiarizationError(f"Échec de la diarisation : {exc}") from exc

        turns: list[SpeakerTurn] = []
        for segment, _track, speaker in annotation.itertracks(yield_label=True):
            turns.append(SpeakerTurn(segment.start, segment.end, speaker))
        return turns


def diarized_transcript(
    segments: list[TranscriptSegment],
    audio_path: Path,
    model: str,
    hf_token: Optional[str],
    progress: ProgressCallback = None,
) -> str:
    """Raccourci : diarise puis renvoie une transcription étiquetée par locuteur."""
    diarizer = Diarizer(model=model, hf_token=hf_token)
    turns = diarizer.diarize(Path(audio_path), progress)
    labeled = assign_speakers(segments, turns)
    return format_labeled_transcript(labeled)


__all__ = [
    "DiarizationError",
    "SpeakerTurn",
    "LabeledSegment",
    "Diarizer",
    "assign_speakers",
    "friendly_speaker_names",
    "format_labeled_transcript",
    "diarized_transcript",
]
