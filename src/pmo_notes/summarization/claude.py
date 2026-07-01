"""Backend de synthèse via l'API Claude d'Anthropic.

À privilégier quand la qualité de synthèse prime et que l'envoi de la
transcription vers l'API Anthropic est acceptable. La clé API est lue depuis la
variable d'environnement `ANTHROPIC_API_KEY`.
"""

from __future__ import annotations

from .base import Summarizer, SummarizerError

# Marge confortable : couvre la réflexion (adaptive thinking) et la synthèse.
# Le streaming évite les délais d'expiration HTTP sur les transcriptions longues.
_MAX_TOKENS = 16_000


class ClaudeSummarizer(Summarizer):
    """Synthèse via le SDK officiel `anthropic` (Messages API, en streaming)."""

    name = "API Claude (Anthropic)"

    def __init__(
        self,
        model: str = "claude-opus-4-8",
        effort: str = "medium",
        api_key: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.model = model
        self.effort = effort
        self._api_key = api_key
        self._client = None  # initialisation paresseuse

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - dépendance manquante
            raise SummarizerError(
                "Le paquet « anthropic » est requis pour le backend Claude "
                "(pip install anthropic)."
            ) from exc

        try:
            # Sans api_key explicite, le SDK lit ANTHROPIC_API_KEY.
            self._client = (
                anthropic.Anthropic(api_key=self._api_key)
                if self._api_key
                else anthropic.Anthropic()
            )
        except Exception as exc:  # clé absente / invalide au moment de l'init
            raise SummarizerError(
                "Impossible d'initialiser le client Anthropic. Vérifie que la "
                "variable d'environnement ANTHROPIC_API_KEY est définie."
            ) from exc
        return self._client

    def _complete(self, system_prompt: str, user_prompt: str) -> str:
        import anthropic

        client = self._get_client()
        try:
            # Streaming + adaptive thinking : recommandé pour une entrée longue
            # et un raisonnement non trivial (Opus 4.8).
            with client.messages.stream(
                model=self.model,
                max_tokens=_MAX_TOKENS,
                thinking={"type": "adaptive"},
                output_config={"effort": self.effort},
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            ) as stream:
                final = stream.get_final_message()
        except anthropic.AuthenticationError as exc:
            raise SummarizerError(
                "Clé API Anthropic invalide ou absente. Définis ANTHROPIC_API_KEY "
                "avec une clé valide."
            ) from exc
        except anthropic.RateLimitError as exc:
            raise SummarizerError(
                "Limite de débit atteinte sur l'API Anthropic. Réessaie dans "
                "quelques instants."
            ) from exc
        except anthropic.APIConnectionError as exc:
            raise SummarizerError(
                "Connexion à l'API Anthropic impossible. Vérifie ta connexion "
                "internet."
            ) from exc
        except anthropic.APIStatusError as exc:
            raise SummarizerError(
                f"L'API Anthropic a renvoyé une erreur {exc.status_code} : {exc.message}"
            ) from exc

        # On ne conserve que le texte (on ignore les blocs de réflexion).
        text = "".join(
            block.text for block in final.content if getattr(block, "type", None) == "text"
        ).strip()
        if not text:
            raise SummarizerError("L'API Claude a renvoyé une réponse vide.")
        return text


__all__ = ["ClaudeSummarizer"]
