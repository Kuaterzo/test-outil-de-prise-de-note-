import json

from pmo_notes.action_register import extract_actions
from pmo_notes.prompts import SYNTHESIS_SYSTEM_PROMPT
from pmo_notes.templates import (
    BUILTIN_TEMPLATES,
    get_template,
    list_templates,
    load_custom_templates,
    load_templates,
)


def test_standard_uses_existing_prompt():
    assert get_template("standard").to_system_prompt() == SYNTHESIS_SYSTEM_PROMPT


def test_unknown_template_falls_back_to_standard():
    assert get_template("inexistant").key == "standard"


def test_copil_prompt_has_sections_and_rules():
    prompt = BUILTIN_TEMPLATES["copil"].to_system_prompt()
    assert "## Introduction" in prompt
    assert "## Actions et responsables" in prompt
    assert "Risques" in prompt
    assert "Règles impératives" in prompt  # postambule partagé


def test_list_templates_starts_with_standard():
    pairs = list_templates()
    assert pairs[0][0] == "standard"
    keys = [k for k, _ in pairs]
    assert {"copil", "atelier", "retrospective", "point_avancement"} <= set(keys)


def test_actions_section_is_extractable_for_every_builtin():
    # Le registre d'actions repère la section dont le titre contient « action ».
    for key, tpl in BUILTIN_TEMPLATES.items():
        if tpl.system_prompt_override is not None:
            continue
        titles = [t.lower() for t, _ in tpl.sections]
        assert any("action" in t for t in titles), key


def test_extract_actions_on_copil_section():
    synthesis = (
        "## Décisions prises\nDécision A.\n\n"
        "## Actions et responsables\n- **Bob** — préparer le budget (lundi)\n"
    )
    items = extract_actions(synthesis, meeting="COPIL", date="2026-06-26")
    assert len(items) == 1
    assert items[0].responsable == "Bob"
    assert items[0].echeance == "lundi"


def test_load_custom_templates(tmp_path):
    path = tmp_path / "templates.json"
    path.write_text(
        json.dumps(
            {"flash": {"name": "Réunion flash", "sections": [["Points", "..."], ["Actions", "..."]]}}
        ),
        encoding="utf-8",
    )
    custom = load_custom_templates(path)
    assert "flash" in custom
    assert custom["flash"].name == "Réunion flash"

    merged = load_templates(custom_path=path)
    assert "flash" in merged and "standard" in merged
