from datetime import datetime

import pytest

from pmo_notes.export import (
    build_basename,
    parse_inline,
    parse_markdown,
    render_docx,
    render_pdf,
    save_synthesis,
    slugify,
)

SAMPLE = (
    "## Introduction\n"
    "Réunion de cadrage.\n\n"
    "## Actions à venir\n"
    "- **Alice** — rédiger le plan (vendredi)\n"
    "- **Bob** — valider le budget\n"
)


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


def test_parse_inline_bold():
    assert parse_inline("**Alice** — action") == [("Alice", True), (" — action", False)]


def test_parse_markdown_blocks():
    blocks = parse_markdown(SAMPLE)
    assert ("h2", "Introduction") in blocks
    assert ("h2", "Actions à venir") in blocks
    bullets = [text for kind, text in blocks if kind == "bullet"]
    assert len(bullets) == 2
    assert bullets[0].startswith("**Alice**")


def test_render_docx_creates_file(tmp_path):
    pytest.importorskip("docx")
    path = render_docx(SAMPLE, tmp_path / "synthese.docx", "Réunion de cadrage")
    assert path.exists() and path.stat().st_size > 0
    # Un .docx est une archive ZIP : signature « PK ».
    assert path.read_bytes()[:2] == b"PK"


def test_render_pdf_creates_file(tmp_path):
    pytest.importorskip("reportlab")
    path = render_pdf(SAMPLE, tmp_path / "synthese.pdf", "Réunion de cadrage")
    assert path.exists() and path.stat().st_size > 0
    assert path.read_bytes()[:4] == b"%PDF"
