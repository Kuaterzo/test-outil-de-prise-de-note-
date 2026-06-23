"""Moteurs de synthèse et fabrique de sélection selon la configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import Summarizer, SummarizerError, chunk_text

if TYPE_CHECKING:  # évite d'importer config au runtime ici
    from ..config import Config


def get_summarizer(config: "Config") -> Summarizer:
    """Instancie le backend de synthèse correspondant à `config.backend`.

    Les backends concrets sont importés paresseusement afin de ne pas exiger
    `requests` (Ollama) ou `anthropic` (Claude) tant qu'ils ne sont pas utilisés.
    """
    backend = (config.backend or "ollama").lower()

    if backend == "ollama":
        from .ollama import OllamaSummarizer

        return OllamaSummarizer(model=config.ollama_model, host=config.ollama_host)

    if backend == "claude":
        from .claude import ClaudeSummarizer

        return ClaudeSummarizer(model=config.claude_model, effort=config.claude_effort)

    raise SummarizerError(
        f"Backend de synthèse inconnu : « {config.backend} ». "
        "Valeurs possibles : ollama, claude."
    )


__all__ = ["Summarizer", "SummarizerError", "chunk_text", "get_summarizer"]
