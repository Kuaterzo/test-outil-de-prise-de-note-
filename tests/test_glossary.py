from pmo_notes.glossary import build_whisper_prompt, parse_terms
from pmo_notes.prompts import MeetingContext, build_synthesis_user_prompt


def test_parse_terms_splits_and_dedupes():
    terms = parse_terms("ACME, SIRH ; Kubernetes\nACME")
    assert terms == ["ACME", "SIRH", "Kubernetes"]


def test_parse_terms_empty():
    assert parse_terms("") == []
    assert parse_terms("   ,  ; \n") == []


def test_build_whisper_prompt():
    prompt = build_whisper_prompt(["ACME", "SIRH"], "Migration du SI RH.")
    assert "ACME" in prompt and "SIRH" in prompt
    assert "Migration du SI RH." in prompt


def test_build_whisper_prompt_empty():
    assert build_whisper_prompt([], "") == ""


def test_context_block_renders_glossary_and_note():
    ctx = MeetingContext(glossary=["ACME", "SIRH"], context_note="Projet Phénix.")
    block = ctx.context_block()
    assert "ACME" in block and "SIRH" in block
    assert "Projet Phénix." in block


def test_context_block_empty_by_default():
    assert MeetingContext().context_block() == ""


def test_user_prompt_includes_context_when_present():
    ctx = MeetingContext(title="COPIL", glossary=["ACME"], context_note="Projet Phénix.")
    prompt = build_synthesis_user_prompt("transcription", ctx)
    assert "ACME" in prompt
    assert "Projet Phénix." in prompt


def test_user_prompt_without_context_unchanged():
    ctx = MeetingContext(title="COPIL")
    prompt = build_synthesis_user_prompt("bonjour", ctx)
    assert "Glossaire" not in prompt
    assert "bonjour" in prompt
