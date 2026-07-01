from pmo_notes.prompts import (
    SYNTHESIS_SYSTEM_PROMPT,
    MeetingContext,
    build_synthesis_user_prompt,
)

REQUIRED_SECTIONS = [
    "## Introduction",
    "## Résumé des échanges",
    "## Actions à venir",
    "## Conclusion",
]


def test_system_prompt_contains_all_sections():
    for section in REQUIRED_SECTIONS:
        assert section in SYNTHESIS_SYSTEM_PROMPT


def test_user_prompt_includes_transcript_and_metadata():
    ctx = MeetingContext(title="Comité de pilotage", participants=["Alice", "Bob"])
    prompt = build_synthesis_user_prompt("Bonjour à tous, commençons.", ctx)
    assert "Comité de pilotage" in prompt
    assert "Alice, Bob" in prompt
    assert "Bonjour à tous" in prompt
    assert "<transcription>" in prompt


def test_participants_line_defaults_when_empty():
    assert MeetingContext().participants_line() == "non précisés"
