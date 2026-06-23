"""Orchestration : enregistrement → transcription → synthèse → export.

Le pipeline relie les briques entre elles et expose deux points d'entrée :

* :meth:`MeetingPipeline.process_recording` — à partir d'un signal capturé,
* :meth:`MeetingPipeline.process_audio_file` — à partir d'un fichier audio existant.

Les modules lourds (audio, transcription) sont importés paresseusement.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from .export import build_basename, save_synthesis
from .prompts import MeetingContext
from .summarization import get_summarizer

if TYPE_CHECKING:
    import numpy as np

    from .config import Config
    from .transcription import Transcriber

ProgressCallback = Optional[Callable[[str], None]]


class PipelineError(RuntimeError):
    """Erreur de haut niveau du pipeline de traitement."""


@dataclass
class MeetingResult:
    """Résultat complet du traitement d'une réunion."""

    transcript: str
    synthesis: str
    synthesis_path: Path
    transcript_path: Optional[Path] = None
    audio_path: Optional[Path] = None


class MeetingPipeline:
    """Chaîne de traitement complète, pilotée par une :class:`Config`."""

    def __init__(self, config: "Config") -> None:
        self.config = config
        self._transcriber: Optional["Transcriber"] = None
        self._transcriber_key: Optional[tuple] = None

    # ----------------------------------------------------------- points d'entrée
    def process_recording(
        self,
        audio: "np.ndarray",
        samplerate: int,
        context: MeetingContext,
        progress: ProgressCallback = None,
        *,
        when: Optional[datetime] = None,
    ) -> MeetingResult:
        """Traite un signal audio capturé en mémoire."""
        from .audio import save_wav

        when = when or datetime.now()
        out_dir = self.config.resolved_output_dir()
        basename = build_basename(context.title, when)

        if self.config.keep_audio:
            audio_path = save_wav(out_dir / f"{basename}.wav", audio, samplerate)
            wav_for_transcription = audio_path
        else:
            audio_path = None
            wav_for_transcription = Path(tempfile.gettempdir()) / f"pmo_{basename}.wav"
            save_wav(wav_for_transcription, audio, samplerate)

        try:
            return self.process_audio_file(
                wav_for_transcription,
                context,
                progress,
                when=when,
                _audio_path=audio_path,
            )
        finally:
            if not self.config.keep_audio:
                try:
                    wav_for_transcription.unlink()
                except OSError:
                    pass

    def process_audio_file(
        self,
        audio_path: Path,
        context: MeetingContext,
        progress: ProgressCallback = None,
        *,
        when: Optional[datetime] = None,
        _audio_path: Optional[Path] = None,
    ) -> MeetingResult:
        """Transcrit puis synthétise un fichier audio, et exporte le résultat."""
        transcriber = self._get_transcriber()
        transcript = transcriber.transcribe(Path(audio_path), progress)
        if not transcript.strip():
            raise PipelineError(
                "La transcription est vide : aucune parole n'a été détectée dans "
                "l'enregistrement."
            )

        summarizer = get_summarizer(self.config)
        if progress:
            progress(f"Synthèse via {summarizer.name}…")
        synthesis = summarizer.summarize(transcript, context, progress)

        when = when or datetime.now()
        if progress:
            progress("Enregistrement de la synthèse…")
        paths = save_synthesis(
            synthesis,
            self.config.resolved_output_dir(),
            context.title,
            transcript=transcript if self.config.save_transcript else None,
            when=when,
        )

        return MeetingResult(
            transcript=transcript,
            synthesis=synthesis,
            synthesis_path=paths["synthesis"],
            transcript_path=paths.get("transcript"),
            audio_path=_audio_path,
        )

    # ----------------------------------------------------------------- interne
    def _get_transcriber(self) -> "Transcriber":
        """Construit (et met en cache) le transcripteur Whisper."""
        from .transcription import Transcriber

        key = (
            self.config.whisper_model,
            self.config.whisper_device,
            self.config.whisper_compute_type,
            self.config.language,
        )
        if self._transcriber is None or self._transcriber_key != key:
            self._transcriber = Transcriber(
                model_size=self.config.whisper_model,
                device=self.config.whisper_device,
                compute_type=self.config.whisper_compute_type,
                language=self.config.language,
            )
            self._transcriber_key = key
        return self._transcriber


__all__ = ["MeetingPipeline", "MeetingResult", "PipelineError"]
