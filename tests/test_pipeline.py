from datetime import datetime

import pytest

from pmo_notes.config import Config
from pmo_notes.pipeline import MeetingDraft, MeetingPipeline, PipelineError
from pmo_notes.prompts import MeetingContext


def _draft(synthesis="## Introduction\nbrouillon", transcript="transcription"):
    return MeetingDraft(
        synthesis=synthesis,
        transcript=transcript,
        context=MeetingContext(title="COPIL", date="2026-06-26"),
        when=datetime(2026, 6, 26, 9, 0),
    )


def test_finalize_writes_edited_synthesis(tmp_path):
    config = Config(output_dir=str(tmp_path), action_register=True, email_enabled=False)
    pipeline = MeetingPipeline(config)
    edited = (
        "## Introduction\nversion corrigée\n\n"
        "## Actions à venir\n- **Alice** — faire X (lundi)\n"
    )
    result = pipeline.finalize(_draft(), edited)

    assert result.synthesis_path.exists()
    assert "version corrigée" in result.synthesis_path.read_text(encoding="utf-8")
    # la transcription du brouillon est conservée
    assert result.transcript_path is not None and result.transcript_path.exists()
    # le registre d'actions a été mis à jour (au moins le CSV)
    assert result.register_paths
    assert (tmp_path / "registre_actions.csv").exists()


def test_finalize_uses_draft_when_no_edit(tmp_path):
    config = Config(output_dir=str(tmp_path), action_register=False, email_enabled=False)
    pipeline = MeetingPipeline(config)
    result = pipeline.finalize(_draft(synthesis="texte brouillon"))
    assert result.synthesis == "texte brouillon"


def test_finalize_empty_raises(tmp_path):
    config = Config(output_dir=str(tmp_path), action_register=False, email_enabled=False)
    pipeline = MeetingPipeline(config)
    with pytest.raises(PipelineError):
        pipeline.finalize(_draft(synthesis=""), "   ")
