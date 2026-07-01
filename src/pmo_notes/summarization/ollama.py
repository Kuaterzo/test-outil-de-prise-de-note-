"""Backend de synthèse 100 % local via Ollama (https://ollama.com).

La transcription ne quitte jamais la machine : Ollama expose un modèle de
langage local sur `http://localhost:11434`.
"""

from __future__ import annotations

from .base import Summarizer, SummarizerError


class OllamaSummarizer(Summarizer):
    """Synthèse via l'API de chat d'un serveur Ollama local."""

    name = "Ollama (local)"

    def __init__(
        self,
        model: str = "llama3.1",
        host: str = "http://localhost:11434",
        timeout: float = 600.0,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout

    def _complete(self, system_prompt: str, user_prompt: str) -> str:
        # Import paresseux : `requests` n'est requis que pour ce backend.
        try:
            import requests
        except ImportError as exc:  # pragma: no cover - dépendance manquante
            raise SummarizerError(
                "Le paquet « requests » est requis pour le backend Ollama "
                "(pip install requests)."
            ) from exc

        url = f"{self.host}/api/chat"
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {
                # Température basse : on veut une synthèse fidèle, pas créative.
                "temperature": 0.2,
            },
        }

        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
        except requests.exceptions.ConnectionError as exc:
            raise SummarizerError(
                f"Impossible de joindre Ollama sur {self.host}. "
                "Vérifie qu'Ollama est lancé (commande « ollama serve ») et que "
                f"le modèle « {self.model} » est installé (« ollama pull {self.model} »)."
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise SummarizerError(
                "Ollama n'a pas répondu dans le délai imparti. La réunion est "
                "peut-être trop longue pour ce modèle, ou la machine trop chargée."
            ) from exc

        if response.status_code == 404:
            raise SummarizerError(
                f"Le modèle « {self.model} » est introuvable côté Ollama. "
                f"Installe-le avec « ollama pull {self.model} »."
            )
        if not response.ok:
            raise SummarizerError(
                f"Ollama a renvoyé une erreur {response.status_code} : {response.text[:300]}"
            )

        data = response.json()
        message = data.get("message") or {}
        content = (message.get("content") or "").strip()
        if not content:
            raise SummarizerError("Ollama a renvoyé une réponse vide.")
        return content


__all__ = ["OllamaSummarizer"]
