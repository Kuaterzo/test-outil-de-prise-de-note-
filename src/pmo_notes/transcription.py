"""Transcription audio → texte, 100 % locale, via faster-whisper.

`faster-whisper` (réimplémentation efficace de Whisper d'OpenAI) tourne sur CPU
ou GPU et gère très bien le français. Le décodage/rééchantillonnage du fichier
audio est délégué à la bibliothèque (via PyAV), d'où l'usage d'un chemin de
fichier WAV plutôt que d'un tableau brut.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

ProgressCallback = Optional[Callable[[str], None]]


class TranscriptionError(RuntimeError):
    """Erreur de transcription (modèle indisponible, fichier illisible, …)."""


class Transcriber:
    """Enveloppe autour de `faster_whisper.WhisperModel` (chargement paresseux)."""

    def __init__(
        self,
        model_size: str = "small",
        device: str = "auto",
        compute_type: str = "auto",
        language: str = "fr",
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self._model = None  # chargé à la première transcription

    def load(self, progress: ProgressCallback = None) -> None:
        """Charge le modèle Whisper en mémoire (téléchargé au 1er usage)."""
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:  # pragma: no cover - dépendance manquante
            raise TranscriptionError(
                "Le paquet « faster-whisper » est requis pour la transcription "
                "(pip install faster-whisper)."
            ) from exc

        if progress:
            progress(f"Chargement du modèle Whisper « {self.model_size} »…")
        try:
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
        except Exception as exc:
            raise TranscriptionError(
                f"Impossible de charger le modèle Whisper « {self.model_size} » : {exc}"
            ) from exc

    def transcribe(self, audio_path: Path, progress: ProgressCallback = None) -> str:
        """Transcrit un fichier audio et renvoie le texte complet."""
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise TranscriptionError(f"Fichier audio introuvable : {audio_path}")

        self.load(progress)
        if progress:
            progress("Transcription en cours…")

        try:
            segments, info = self._model.transcribe(
                str(audio_path),
                language=self.language,
                vad_filter=True,  # filtre les silences : transcription plus propre
                beam_size=5,
            )
        except Exception as exc:
            raise TranscriptionError(f"Échec de la transcription : {exc}") from exc

        total = getattr(info, "duration", 0.0) or 0.0
        parts: list[str] = []
        for segment in segments:  # itérateur paresseux : le travail se fait ici
            text = segment.text.strip()
            if text:
                parts.append(text)
            if progress and total:
                pct = min(100, int(segment.end / total * 100))
                progress(f"Transcription… {pct} %")

        return " ".join(parts).strip()


__all__ = ["Transcriber", "TranscriptionError"]
