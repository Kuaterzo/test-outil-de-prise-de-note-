import pytest

from pmo_notes.config import Config
from pmo_notes.prompts import SYNTHESIS_SYSTEM_PROMPT, MeetingContext
from pmo_notes.summarization import get_summarizer
from pmo_notes.summarization.base import Summarizer, SummarizerError, chunk_text


class DummySummarizer(Summarizer):
    """Backend factice qui enregistre les appels au lieu d'appeler un modèle."""

    name = "factice"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.calls = []  # liste de (system_prompt, user_prompt)

    def _complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return f"réponse {len(self.calls)}"


def test_factory_returns_ollama_by_default():
    from pmo_notes.summarization.ollama import OllamaSummarizer

    assert isinstance(get_summarizer(Config(backend="ollama")), OllamaSummarizer)


def test_factory_returns_claude():
    from pmo_notes.summarization.claude import ClaudeSummarizer

    summarizer = get_summarizer(Config(backend="claude"))
    assert isinstance(summarizer, ClaudeSummarizer)
    assert summarizer.model == "claude-opus-4-8"


def test_factory_unknown_backend_raises():
    with pytest.raises(SummarizerError):
        get_summarizer(Config(backend="inexistant"))


def test_summarize_empty_transcript_raises():
    with pytest.raises(SummarizerError):
        DummySummarizer().summarize("   ", MeetingContext())


def test_single_pass_uses_synthesis_prompt():
    summ = DummySummarizer(single_pass_limit=10_000)
    result = summ.summarize("Réunion courte.", MeetingContext())
    assert result == "réponse 1"
    assert len(summ.calls) == 1
    assert summ.calls[0][0] == SYNTHESIS_SYSTEM_PROMPT


def test_long_transcript_uses_map_reduce():
    summ = DummySummarizer(single_pass_limit=50, chunk_size=40)
    transcript = "Phrase numéro %d. " % 0 + " ".join(f"Idée {i}." for i in range(60))
    summ.summarize(transcript, MeetingContext())
    # Au moins deux tranches (map) + une réduction finale.
    assert len(summ.calls) >= 3
    # Le dernier appel produit la synthèse structurée.
    assert summ.calls[-1][0] == SYNTHESIS_SYSTEM_PROMPT


def test_summarize_uses_custom_system_prompt():
    summ = DummySummarizer(single_pass_limit=10_000)
    summ.summarize("Réunion.", MeetingContext(), system_prompt="INVITE PERSONNALISÉE")
    assert summ.calls[0][0] == "INVITE PERSONNALISÉE"


def test_chunk_text_short_returns_single():
    assert chunk_text("court", 1000) == ["court"]


def test_chunk_text_splits_long_text():
    text = " ".join(f"mot{i}" for i in range(500))
    chunks = chunk_text(text, 200)
    assert len(chunks) > 1
    assert all(c.strip() for c in chunks)
