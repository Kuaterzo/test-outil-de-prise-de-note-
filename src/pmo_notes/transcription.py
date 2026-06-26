"""Transcription audio → texte, 100 % locale, via faster-whisper.

`faster-whisper` (réimplémentation efficace de Whisper d'OpenAI) tourne sur CPU
ou GPU et gère très bien le français. Le décodage/rééchantillonnage du fichier
audio est délégué à la bibliothèque (via PyAV), d'où l'usage d'un chemin de
fichier WAV plutôt que d'un tableau brut.

La transcription est exposée sous deux formes :

* :meth:`Transcriber.transcribe_segments` — segments horodatés (start, end,
  text), nécessaires à l'alignement avec les locuteurs (diarisation) ;
* :meth:`Transcriber.transcribe` — texte complet, dérivé des segments.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

ProgressCallback = Optional[Callable[[str], None]]


@dataclass
class TranscriptSegment:
    """Portion de transcription horodatée."""

    start: float
    end: float
    text: str


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

    def transcribe_segments(
        self,
        audio_path: Path,
        progress: ProgressCallback = None,
        *,
        initial_prompt: Optional[str] = None,
    ) -> list[TranscriptSegment]:
        """Transcrit un fichier audio et renvoie les segments horodatés.

        `initial_prompt` (glossaire / contexte) oriente la reconnaissance vers
        la bonne orthographe des noms propres et acronymes.
        """
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
                initial_prompt=initial_prompt or None,
            )
        except Exception as exc:
            raise TranscriptionError(f"Échec de la transcription : {exc}") from exc

        total = getattr(info, "duration", 0.0) or 0.0
        result: list[TranscriptSegment] = []
        for segment in segments:  # itérateur paresseux : le travail se fait ici
            text = segment.text.strip()
            if text:
                result.append(TranscriptSegment(segment.start, segment.end, text))
            if progress and total:
                pct = min(100, int(segment.end / total * 100))
                progress(f"Transcription… {pct} %")
        return result

    def transcribe(
        self,
        audio_path: Path,
        progress: ProgressCallback = None,
        *,
        initial_prompt: Optional[str] = None,
    ) -> str:
        """Transcrit un fichier audio et renvoie le texte complet."""
        segments = self.transcribe_segments(
            audio_path, progress, initial_prompt=initial_prompt
        )
        return join_segments(segments)


def join_segments(segments: list[TranscriptSegment]) -> str:
    """Concatène le texte de segments en une transcription continue."""
    return " ".join(s.text for s in segments).strip()


__all__ = ["Transcriber", "TranscriptSegment", "TranscriptionError", "join_segments"]
