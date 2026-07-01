"""Classe de base des moteurs de synthèse.

La logique commune (découpage des longues transcriptions en tranches puis
réduction en une synthèse unique) vit ici. Chaque backend concret n'a qu'à
implémenter `_complete(system_prompt, user_prompt) -> str`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Optional

from ..prompts import (
    CHUNK_SYSTEM_PROMPT,
    SYNTHESIS_SYSTEM_PROMPT,
    MeetingContext,
    build_chunk_user_prompt,
    build_reduce_user_prompt,
    build_synthesis_user_prompt,
)

#: Au-delà de ce nombre de caractères, on passe en mode map-reduce.
#: ~12 000 caractères ≈ 3 000 mots ≈ 20 min de parole : marge confortable
#: pour la plupart des modèles locaux comme pour l'API Claude.
DEFAULT_SINGLE_PASS_LIMIT = 12_000

#: Taille d'une tranche en mode map-reduce.
DEFAULT_CHUNK_SIZE = 9_000

ProgressCallback = Optional[Callable[[str], None]]


class SummarizerError(RuntimeError):
    """Erreur de haut niveau remontée par un backend de synthèse."""


class Summarizer(ABC):
    """Interface commune des moteurs de synthèse."""

    #: Nom lisible du backend (pour les messages et l'IHM).
    name: str = "synthèse"

    def __init__(
        self,
        single_pass_limit: int = DEFAULT_SINGLE_PASS_LIMIT,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> None:
        self.single_pass_limit = single_pass_limit
        self.chunk_size = chunk_size

    # ------------------------------------------------------------- abstrait
    @abstractmethod
    def _complete(self, system_prompt: str, user_prompt: str) -> str:
        """Appelle le modèle et renvoie le texte généré.

        Doit lever `SummarizerError` (avec un message en français) en cas de
        problème de configuration ou de connexion.
        """

    # --------------------------------------------------------------- public
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Appel direct du modèle (utilisé pour des tâches auxiliaires, p. ex.
        l'identification des noms de locuteurs)."""
        return self._complete(system_prompt, user_prompt)

    def summarize(
        self,
        transcript: str,
        context: MeetingContext,
        progress: ProgressCallback = None,
        *,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Produit la synthèse structurée d'une transcription.

        `system_prompt` permet d'imposer la structure d'un modèle de réunion
        (voir :mod:`pmo_notes.templates`) ; à défaut, le modèle standard est
        utilisé.
        """
        system = system_prompt or SYNTHESIS_SYSTEM_PROMPT
        transcript = (transcript or "").strip()
        if not transcript:
            raise SummarizerError("La transcription est vide : rien à synthétiser.")

        if len(transcript) <= self.single_pass_limit:
            self._notify(progress, "Rédaction de la synthèse…")
            return self._complete(
                system,
                build_synthesis_user_prompt(transcript, context),
            ).strip()

        # Réunion longue : map-reduce.
        chunks = chunk_text(transcript, self.chunk_size)
        notes: list[str] = []
        for i, chunk in enumerate(chunks, start=1):
            self._notify(progress, f"Analyse de la portion {i}/{len(chunks)}…")
            note = self._complete(
                CHUNK_SYSTEM_PROMPT,
                build_chunk_user_prompt(chunk, i, len(chunks)),
            ).strip()
            notes.append(f"### Portion {i}\n{note}")

        self._notify(progress, "Assemblage de la synthèse finale…")
        combined = "\n\n".join(notes)
        return self._complete(
            system,
            build_reduce_user_prompt(combined, context),
        ).strip()

    # --------------------------------------------------------------- privé
    @staticmethod
    def _notify(progress: ProgressCallback, message: str) -> None:
        if progress is not None:
            progress(message)


def chunk_text(text: str, chunk_size: int, overlap: int = 200) -> list[str]:
    """Découpe `text` en tranches d'environ `chunk_size` caractères.

    Le découpage privilégie une coupure sur une fin de phrase ou un retour à la
    ligne proche de la limite, et conserve un léger chevauchement entre tranches
    pour préserver le contexte.
    """
    text = text.strip()
    if chunk_size <= 0 or len(text) <= chunk_size:
        return [text] if text else []

    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        if end < n:
            # Cherche une coupure « propre » dans la dernière partie de la tranche.
            window = text[start:end]
            cut = max(window.rfind(". "), window.rfind("\n"), window.rfind("! "), window.rfind("? "))
            if cut > chunk_size * 0.5:
                end = start + cut + 1
        chunks.append(text[start:end].strip())
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c]


__all__ = [
    "Summarizer",
    "SummarizerError",
    "chunk_text",
    "DEFAULT_SINGLE_PASS_LIMIT",
    "DEFAULT_CHUNK_SIZE",
]
