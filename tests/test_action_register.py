import pytest

from pmo_notes.action_register import (
    append_to_csv,
    append_to_xlsx,
    extract_actions,
    update_register,
)

SAMPLE = (
    "## Introduction\n"
    "Réunion de cadrage.\n\n"
    "## Actions à venir\n"
    "- **Alice** — rédiger le plan (vendredi)\n"
    "- **Bob** — valider le budget\n"
    "- relancer le prestataire\n\n"
    "## Conclusion\n"
    "Fin.\n"
)


def test_extract_actions_parses_responsible_and_due():
    items = extract_actions(SAMPLE, meeting="COPIL", date="2026-06-26", source="s.md")
    assert len(items) == 3

    assert items[0].responsable == "Alice"
    assert items[0].action == "rédiger le plan"
    assert items[0].echeance == "vendredi"
    assert items[0].reunion == "COPIL"
    assert items[0].statut == "À faire"

    assert items[1].responsable == "Bob"
    assert items[1].echeance == ""

    # Puce sans responsable explicite
    assert items[2].responsable == "à confirmer"
    assert items[2].action == "relancer le prestataire"


def test_extract_actions_no_section_returns_empty():
    assert extract_actions("## Introduction\nrien", meeting="m", date="d") == []


def test_append_to_csv_creates_then_appends(tmp_path):
    path = tmp_path / "registre_actions.csv"
    items = extract_actions(SAMPLE, meeting="COPIL", date="2026-06-26")

    append_to_csv(path, items)
    lines = [l for l in path.read_text(encoding="utf-8-sig").splitlines() if l.strip()]
    assert lines[0].startswith("Date;Réunion;Responsable")
    assert len(lines) == 1 + 3  # en-tête + 3 actions

    append_to_csv(path, items[:1])
    lines = [l for l in path.read_text(encoding="utf-8-sig").splitlines() if l.strip()]
    assert len(lines) == 1 + 3 + 1  # en-tête conservé, 1 action ajoutée


def test_update_register_returns_paths(tmp_path):
    items = extract_actions(SAMPLE, meeting="COPIL", date="2026-06-26")
    paths = update_register(tmp_path, items)
    assert any(p.name == "registre_actions.csv" for p in paths)
    assert all(p.exists() for p in paths)


def test_update_register_empty_returns_nothing(tmp_path):
    assert update_register(tmp_path, []) == []


def test_append_to_xlsx_appends_rows(tmp_path):
    pytest.importorskip("openpyxl")
    from openpyxl import load_workbook

    path = tmp_path / "registre_actions.xlsx"
    items = extract_actions(SAMPLE, meeting="COPIL", date="2026-06-26")
    append_to_xlsx(path, items)
    append_to_xlsx(path, items[:1])

    worksheet = load_workbook(path).active
    # 1 en-tête + 3 + 1 actions = 5 lignes
    assert worksheet.max_row == 5
    assert [c.value for c in worksheet[1]] == [
        "Date", "Réunion", "Responsable", "Action", "Échéance", "Statut", "Source",
    ]
