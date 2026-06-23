from datetime import datetime

from pmo_notes.export import build_basename, save_synthesis, slugify


def test_slugify_removes_invalid_characters():
    assert slugify('Réunion: budget/Q1 *2026?') == "Réunion_budget_Q1_2026"


def test_slugify_falls_back_when_empty():
    assert slugify("///") == "reunion"


def test_build_basename_format():
    when = datetime(2026, 6, 23, 14, 5)
    assert build_basename("Comité", when) == "2026-06-23_14h05_Comité"


def test_save_synthesis_writes_files(tmp_path):
    when = datetime(2026, 6, 23, 9, 30)
    paths = save_synthesis(
        "## Introduction\nContenu.",
        tmp_path,
        "Point projet",
        transcript="texte brut",
        when=when,
    )
    assert paths["synthesis"].exists()
    assert paths["transcript"].exists()
    assert paths["synthesis"].read_text(encoding="utf-8").startswith("## Introduction")
    assert paths["transcript"].read_text(encoding="utf-8").startswith("texte brut")


def test_save_synthesis_without_transcript(tmp_path):
    paths = save_synthesis("Synthèse", tmp_path, "Sans transcription")
    assert "transcript" not in paths
    assert paths["synthesis"].exists()
