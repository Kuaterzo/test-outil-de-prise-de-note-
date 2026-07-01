"""Glossaire / vocabulaire métier personnalisé.

Le PMO peut fournir des **noms propres, acronymes et termes de projet**. Ils
servent à deux endroits :

* la **transcription** — passés en `initial_prompt` à Whisper, ils orientent la
  reconnaissance vers la bonne orthographe (ACME, SIRH, Kubernetes, prénoms…) ;
* la **synthèse** — fournis en contexte au modèle, pour une terminologie juste.

La logique de ce module est *pure* (sans dépendance) et testable.
"""

from __future__ import annotations

import re

_SEPARATORS = re.compile(r"[,;\n]+")


def parse_terms(text: str) -> list[str]:
    """Découpe une saisie libre (virgules, points-virgules, retours ligne) en
    liste de termes, en supprimant les doublons (insensible à la casse)."""
    if not text:
        return []
    terms: list[str] = []
    seen: set[str] = set()
    for part in _SEPARATORS.split(text):
        term = part.strip()
        if term and term.lower() not in seen:
            seen.add(term.lower())
            terms.append(term)
    return terms


def build_whisper_prompt(terms: list[str], context_note: str = "") -> str:
    """Construit l'« initial_prompt » Whisper à partir des termes et du contexte.

    Whisper se laisse guider par le vocabulaire présent dans ce texte : on y
    énumère donc les termes attendus, suivis d'une éventuelle note de contexte.
    """
    pieces: list[str] = []
    if terms:
        pieces.append("Termes et noms propres : " + ", ".join(terms) + ".")
    note = (context_note or "").strip()
    if note:
        pieces.append(note)
    return " ".join(pieces).strip()


__all__ = ["parse_terms", "build_whisper_prompt"]
