"""Orchestration : enregistrement → transcription → synthèse → export.

Le traitement se décompose en deux phases, ce qui permet une **relecture/édition
de la synthèse avant diffusion** :

1. *génération* du brouillon — :meth:`MeetingPipeline.generate_from_recording`
   / :meth:`MeetingPipeline.generate_from_file` → un :class:`MeetingDraft` ;
2. *finalisation* — :meth:`MeetingPipeline.finalize` enregistre, exporte, met à
   jour le registre et envoie l'e-mail, à partir de la synthèse (éventuellement
   corrigée).

Les méthodes :meth:`process_recording` / :meth:`process_audio_file` enchaînent
les deux phases d'un coup (comportement « sans relecture »).

Les modules lourds (audio, transcription) sont importés paresseusement.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from .export import build_basename, render_docx, render_pdf, save_synthesis
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
    docx_path: Optional[Path] = None
    pdf_path: Optional[Path] = None
    register_paths: list = field(default_factory=list)
    email_sent: bool = False

    def all_paths(self) -> list[Path]:
        """Tous les fichiers produits, dans l'ordre de lecture le plus utile."""
        candidates = [
            self.synthesis_path,
            self.docx_path,
            self.pdf_path,
            self.transcript_path,
            self.audio_path,
        ]
        return [p for p in candidates if p is not None]


@dataclass
class MeetingDraft:
    """Brouillon de synthèse, avant enregistrement/diffusion (phase de relecture)."""

    synthesis: str
    transcript: str
    context: MeetingContext
    when: datetime
    audio_path: Optional[Path] = None


class MeetingPipeline:
    """Chaîne de traitement complète, pilotée par une :class:`Config`."""

    def __init__(self, config: "Config") -> None:
        self.config = config
        self._transcriber: Optional["Transcriber"] = None
        self._transcriber_key: Optional[tuple] = None

    # ----------------------------------------------------------- bout en bout
    def process_recording(
        self,
        audio: "np.ndarray",
        samplerate: int,
        context: MeetingContext,
        progress: ProgressCallback = None,
        *,
        when: Optional[datetime] = None,
    ) -> MeetingResult:
        """Traite un signal capturé de bout en bout (génération + finalisation)."""
        draft = self.generate_from_recording(audio, samplerate, context, progress, when=when)
        return self.finalize(draft, draft.synthesis, progress)

    def process_audio_file(
        self,
        audio_path: Path,
        context: MeetingContext,
        progress: ProgressCallback = None,
        *,
        when: Optional[datetime] = None,
        _audio_path: Optional[Path] = None,
    ) -> MeetingResult:
        """Traite un fichier audio de bout en bout (génération + finalisation)."""
        draft = self.generate_from_file(
            audio_path, context, progress, when=when, kept_audio_path=_audio_path
        )
        return self.finalize(draft, draft.synthesis, progress)

    # --- Phase 1 : génération du brouillon de synthèse ----------------------
    def generate_from_recording(
        self,
        audio: "np.ndarray",
        samplerate: int,
        context: MeetingContext,
        progress: ProgressCallback = None,
        *,
        when: Optional[datetime] = None,
    ) -> MeetingDraft:
        """Transcrit et synthétise un signal capturé, sans rien exporter encore."""
        from .audio import save_wav

        when = when or datetime.now()
        out_dir = self.config.resolved_output_dir()
        basename = build_basename(context.title, when)

        if self.config.keep_audio:
            audio_path = save_wav(out_dir / f"{basename}.wav", audio, samplerate)
            source = audio_path
        else:
            audio_path = None
            source = Path(tempfile.gettempdir()) / f"pmo_{basename}.wav"
            save_wav(source, audio, samplerate)

        try:
            return self.generate_from_file(
                source, context, progress, when=when, kept_audio_path=audio_path
            )
        finally:
            if not self.config.keep_audio:
                try:
                    source.unlink()
                except OSError:
                    pass

    def generate_from_file(
        self,
        audio_path: Path,
        context: MeetingContext,
        progress: ProgressCallback = None,
        *,
        when: Optional[datetime] = None,
        kept_audio_path: Optional[Path] = None,
    ) -> MeetingDraft:
        """Transcrit et synthétise un fichier audio ; renvoie un brouillon à relire."""
        transcriber = self._get_transcriber()
        segments = transcriber.transcribe_segments(Path(audio_path), progress)
        if not segments:
            raise PipelineError(
                "La transcription est vide : aucune parole n'a été détectée dans "
                "l'enregistrement."
            )
        transcript = self._build_transcript(segments, Path(audio_path), progress)

        summarizer = get_summarizer(self.config)
        if self.config.diarization and self.config.infer_speaker_names:
            transcript = self._name_speakers(summarizer, transcript, progress)

        from .templates import get_template

        template = get_template(self.config.synthesis_template)
        if progress:
            progress(f"Synthèse via {summarizer.name} (modèle : {template.name})…")
        synthesis = summarizer.summarize(
            transcript, context, progress, system_prompt=template.to_system_prompt()
        )
        return MeetingDraft(
            synthesis=synthesis,
            transcript=transcript,
            context=context,
            when=when or datetime.now(),
            audio_path=kept_audio_path,
        )

    # --- Phase 2 : finalisation (enregistrement, export, registre, e-mail) --
    def finalize(
        self,
        draft: MeetingDraft,
        synthesis: Optional[str] = None,
        progress: ProgressCallback = None,
    ) -> MeetingResult:
        """Enregistre et diffuse la synthèse (éventuellement relue/éditée).

        `synthesis` permet de fournir une version corrigée du brouillon ; à
        défaut, le texte du brouillon est utilisé tel quel.
        """
        synthesis = (synthesis if synthesis is not None else draft.synthesis).strip()
        if not synthesis:
            raise PipelineError("La synthèse est vide : rien à enregistrer.")
        context = draft.context
        when = draft.when
        out_dir = self.config.resolved_output_dir()

        if progress:
            progress("Enregistrement de la synthèse…")
        paths = save_synthesis(
            synthesis,
            out_dir,
            context.title,
            transcript=draft.transcript if self.config.save_transcript else None,
            when=when,
        )

        basename = build_basename(context.title, when)
        docx_path = pdf_path = None
        if self.config.export_docx:
            docx_path = self._export_document(
                render_docx, synthesis, out_dir / f"{basename}.docx", context.title,
                "Word (.docx)", progress,
            )
        if self.config.export_pdf:
            pdf_path = self._export_document(
                render_pdf, synthesis, out_dir / f"{basename}.pdf", context.title,
                "PDF", progress,
            )

        result = MeetingResult(
            transcript=draft.transcript,
            synthesis=synthesis,
            synthesis_path=paths["synthesis"],
            transcript_path=paths.get("transcript"),
            audio_path=draft.audio_path,
            docx_path=docx_path,
            pdf_path=pdf_path,
        )

        if self.config.action_register:
            self._update_action_register(result, context, progress)
        if self.config.email_enabled:
            self._send_email(result, context, progress)
        return result

    def _update_action_register(self, result: "MeetingResult", context, progress: ProgressCallback) -> None:
        """Ajoute les actions de la synthèse au registre cumulatif (xlsx/csv)."""
        try:
            from .action_register import extract_actions, update_register

            items = extract_actions(
                result.synthesis,
                meeting=context.title,
                date=context.date,
                source=result.synthesis_path.name,
            )
            if not items:
                return
            if progress:
                progress(f"Mise à jour du registre d'actions ({len(items)} action(s))…")
            result.register_paths = update_register(
                self.config.resolved_output_dir(), items
            )
        except Exception as exc:  # repli gracieux
            if progress:
                progress(f"Registre d'actions non mis à jour ({exc}).")

    def _send_email(self, result: "MeetingResult", context, progress: ProgressCallback) -> None:
        """Envoie la synthèse par e-mail (pièces jointes md/docx/pdf).

        N'interrompt jamais le traitement : un échec d'envoi est signalé mais la
        synthèse reste produite et enregistrée localement.
        """
        try:
            from .email_sender import send_synthesis_email

            if progress:
                progress("Envoi de la synthèse par e-mail…")
            attachments = [
                p for p in (result.synthesis_path, result.docx_path, result.pdf_path) if p
            ]
            recipients = send_synthesis_email(
                self.config,
                subject=f"Synthèse de réunion — {context.title}",
                body=result.synthesis,
                attachments=attachments,
            )
            result.email_sent = True
            if progress:
                progress(f"E-mail envoyé à {', '.join(recipients)}.")
        except Exception as exc:  # repli gracieux
            if progress:
                progress(f"Envoi e-mail échoué ({exc}).")

    @staticmethod
    def _export_document(renderer, synthesis, path, title, label, progress):
        """Génère un document (docx/pdf) ; n'interrompt pas en cas d'échec."""
        try:
            if progress:
                progress(f"Génération du document {label}…")
            return renderer(synthesis, path, title)
        except Exception as exc:  # dépendance manquante, erreur de rendu…
            if progress:
                progress(f"Export {label} ignoré ({exc}).")
            return None

    # ----------------------------------------------------------------- interne
    @staticmethod
    def _name_speakers(summarizer, transcript: str, progress: ProgressCallback) -> str:
        """Remplace « Locuteur N » par les vrais noms si on peut les déduire.

        N'interrompt jamais le traitement : en cas d'échec, la transcription
        étiquetée d'origine est conservée.
        """
        if "Locuteur " not in transcript:
            return transcript  # pas de diarisation exploitable
        try:
            from .speaker_names import name_speakers

            if progress:
                progress("Identification des noms des locuteurs…")
            renamed, mapping = name_speakers(summarizer, transcript)
            if progress and mapping:
                progress(
                    f"{len(mapping)} locuteur(s) nommé(s) : " + ", ".join(mapping.values())
                )
            return renamed
        except Exception as exc:  # repli gracieux
            if progress:
                progress(f"Noms des locuteurs non déterminés ({exc}).")
            return transcript

    def _build_transcript(self, segments, audio_path: Path, progress: ProgressCallback) -> str:
        """Construit la transcription, avec ou sans étiquettes de locuteurs.

        Si la diarisation est activée mais échoue (dépendance ou jeton manquant,
        erreur du modèle), on retombe sur une transcription simple en signalant
        la raison plutôt que d'interrompre tout le traitement.
        """
        from .transcription import join_segments

        if not self.config.diarization:
            return join_segments(segments)

        try:
            from .diarization import diarized_transcript

            if progress:
                progress("Diarisation (identification des locuteurs)…")
            return diarized_transcript(
                segments,
                audio_path,
                model=self.config.diarization_model,
                hf_token=self.config.hf_token,
                progress=progress,
            )
        except Exception as exc:  # repli gracieux
            if progress:
                progress(f"Diarisation ignorée ({exc}). Transcription simple utilisée.")
            return join_segments(segments)

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


__all__ = ["MeetingPipeline", "MeetingResult", "MeetingDraft", "PipelineError"]
