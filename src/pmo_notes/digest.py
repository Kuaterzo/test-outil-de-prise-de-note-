"""Digest / rapport de projet consolidé à partir de plusieurs synthèses.

Agrège les synthèses de réunions d'un dossier (sur une période éventuelle) en un
rapport transversal : vue d'ensemble, décisions clés, actions en cours, risques
et prochaines étapes. Réutilise le moteur de synthèse configuré.

La collecte des fichiers et la construction de l'invite sont *pures* (testables) ;
l'appel au modèle est délégué à un :class:`~pmo_notes.summarization.base.Summarizer`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .summarization.base import Summarizer

# Reconnaît un fichier de synthèse de réunion « AAAA-MM-JJ_HHhMM_Titre.md ».
# Exclut de fait les digests (« digest_… ») et les transcriptions (.txt).
_MEETING_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})_\d{2}h\d{2}_.+\.md$")


class DigestError(RuntimeError):
    """Erreur de génération du digest de projet."""


DIGEST_SYSTEM_PROMPT = """\
Tu es l'assistant d'un PMO. On te fournit plusieurs synthèses de réunions d'un \
même projet, dans l'ordre chronologique. Produis un RAPPORT DE PROJET consolidé, \
en français, au format Markdown, en respectant EXACTEMENT cette structure :

## Vue d'ensemble
Point de situation global du projet sur la période couverte. 3 à 5 phrases.

## Avancement et décisions clés
Principales avancées et décisions prises au fil des réunions (puces), sans \
répétitions.

## Actions en cours et à venir
Synthèse des actions encore ouvertes ou à venir, avec le responsable et \
l'échéance lorsqu'ils sont connus, au format « **Responsable** — action \
(échéance) ». Regroupe les actions liées plutôt que de recopier chaque réunion.

## Risques et points d'attention
Risques, alertes et points de vigilance récurrents ou non résolus.

## Prochaines étapes
Priorités et jalons à venir.

Règles impératives :
- Appuie-toi UNIQUEMENT sur les synthèses fournies ; n'invente rien.
- Consolide et dédoublonne : privilégie une vision transversale plutôt qu'une \
simple concaténation.
- Si une information est incertaine ou en suspens, signale-la avec « [à confirmer] ».
- Ne produis que le rapport.
"""


@dataclass
class SynthesisDoc:
    """Une synthèse de réunion retenue pour le digest."""

    date: str
    name: str
    text: str


def collect_syntheses(
    output_dir: Path,
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> list[SynthesisDoc]:
    """Collecte les synthèses de réunions du dossier, triées chronologiquement.

    `since` / `until` filtrent par date (chaînes ISO « AAAA-MM-JJ », comparées
    lexicographiquement, ce qui est correct pour ce format).
    """
    output_dir = Path(output_dir)
    docs: list[SynthesisDoc] = []
    if not output_dir.exists():
        return docs
    for path in output_dir.glob("*.md"):
        match = _MEETING_RE.match(path.name)
        if not match:
            continue
        when = match.group("date")
        if since and when < since:
            continue
        if until and when > until:
            continue
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            docs.append(SynthesisDoc(date=when, name=path.name, text=text))
    docs.sort(key=lambda d: (d.date, d.name))
    return docs


def build_digest_user_prompt(docs: list[SynthesisDoc], title: str) -> str:
    """Construit l'invite à partir des synthèses collectées."""
    header = (
        f"Projet : {title}\n"
        f"Nombre de réunions : {len(docs)}\n"
        f"Période : {docs[0].date} → {docs[-1].date}\n\n"
        "Synthèses des réunions, dans l'ordre chronologique :"
    )
    blocks = [
        f'<reunion date="{doc.date}">\n{doc.text}\n</reunion>' for doc in docs
    ]
    return header + "\n\n" + "\n\n".join(blocks)


def make_digest(summarizer: "Summarizer", docs: list[SynthesisDoc], title: str = "Projet") -> str:
    """Produit le rapport de projet consolidé à partir des synthèses."""
    if not docs:
        raise DigestError("Aucune synthèse à consolider.")
    return summarizer.complete(
        DIGEST_SYSTEM_PROMPT, build_digest_user_prompt(docs, title)
    ).strip()


__all__ = [
    "DigestError",
    "SynthesisDoc",
    "DIGEST_SYSTEM_PROMPT",
    "collect_syntheses",
    "build_digest_user_prompt",
    "make_digest",
]
