"""Construction des invites (prompts) de synthèse de réunion.

Ces invites sont partagées par tous les backends (Ollama local, API Claude) afin
que la structure de la synthèse soit identique quel que soit le moteur choisi.

Structure imposée de la synthèse (en français, format Markdown) :

* une introduction,
* un résumé des échanges de la réunion,
* les actions futures, y compris les personnes concernées,
* une conclusion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as _date
from typing import Optional


@dataclass
class MeetingContext:
    """Métadonnées d'une réunion utilisées pour contextualiser la synthèse."""

    title: str = "Réunion"
    date: str = field(default_factory=lambda: _date.today().isoformat())
    participants: list[str] = field(default_factory=list)
    language: str = "fr"

    def participants_line(self) -> str:
        """Représentation lisible des participants, ou « non précisés »."""
        names = [p.strip() for p in self.participants if p.strip()]
        return ", ".join(names) if names else "non précisés"


# Persona + consignes de rédaction. Volontairement strict sur la fidélité au
# contenu : l'outil doit synthétiser, pas inventer.
SYNTHESIS_SYSTEM_PROMPT = """\
Tu es l'assistant d'un PMO (Project Management Officer) chargé de rédiger la \
synthèse écrite d'une réunion à partir de sa transcription audio.

La transcription est issue d'une reconnaissance vocale automatique : elle peut \
contenir des erreurs, des hésitations, des répétitions ou une ponctuation \
approximative. Reconstitue le sens sans inventer d'informations absentes.

Rédige une synthèse professionnelle, claire et concise, en français, au format \
Markdown, en respectant EXACTEMENT la structure suivante :

## Introduction
Contexte de la réunion : objet, cadre, participants si identifiables. 2 à 4 phrases.

## Résumé des échanges
Synthèse fidèle des points abordés et des décisions prises, organisée par thème \
sous forme de puces ou de courts paragraphes. Reste factuel.

## Actions à venir
Liste des actions décidées. Pour CHAQUE action, précise la personne concernée \
(le responsable) et l'échéance lorsqu'elle est mentionnée. Utilise une puce par \
action au format : « **Responsable** — action à mener (échéance) ». Si le \
responsable ou l'échéance n'est pas explicite dans la transcription, indique \
« responsable à confirmer » ou « échéance à confirmer » plutôt que de l'inventer.

## Conclusion
Bilan en 2 à 4 phrases : points clés, prochaines étapes, éventuels points ouverts.

Règles impératives :
- N'invente jamais de noms, de chiffres, de dates ou d'engagements absents de la \
transcription.
- Si une information est ambiguë ou inaudible, signale-la avec « [à confirmer] ».
- Ne commente pas ton propre travail : produis uniquement la synthèse.
- Conserve les titres de sections ci-dessus à l'identique.
"""


def build_synthesis_user_prompt(transcript: str, context: MeetingContext) -> str:
    """Invite utilisateur finale : métadonnées + transcription à synthétiser."""
    return (
        f"Titre de la réunion : {context.title}\n"
        f"Date : {context.date}\n"
        f"Participants : {context.participants_line()}\n\n"
        "Voici la transcription de la réunion à synthétiser :\n\n"
        "<transcription>\n"
        f"{transcript.strip()}\n"
        "</transcription>"
    )


# --- Cartographie / réduction pour les longues réunions --------------------
# Pour une réunion trop longue pour tenir confortablement dans une seule
# requête, on résume d'abord chaque tranche (map) avant de produire la
# synthèse structurée finale à partir des notes intermédiaires (reduce).

CHUNK_SYSTEM_PROMPT = """\
Tu assistes un PMO. On te donne une PORTION d'une transcription de réunion \
(reconnaissance vocale, donc imparfaite). Produis des notes factuelles et \
concises (puces) couvrant : les sujets abordés, les décisions prises, et toute \
action évoquée avec la personne concernée et l'échéance si elles sont citées. \
N'invente rien. Ne rédige pas d'introduction ni de conclusion : uniquement les \
notes de cette portion.
"""


def build_chunk_user_prompt(chunk: str, index: int, total: int) -> str:
    """Invite pour résumer une tranche de transcription (étape « map »)."""
    return (
        f"Portion {index}/{total} de la transcription :\n\n"
        "<portion>\n"
        f"{chunk.strip()}\n"
        "</portion>"
    )


def build_reduce_user_prompt(notes: str, context: MeetingContext) -> str:
    """Invite finale à partir des notes de toutes les tranches (étape « reduce »)."""
    return (
        f"Titre de la réunion : {context.title}\n"
        f"Date : {context.date}\n"
        f"Participants : {context.participants_line()}\n\n"
        "Voici les notes prises sur les différentes portions de la réunion, dans "
        "l'ordre chronologique. Rédige la synthèse finale en respectant la "
        "structure imposée.\n\n"
        "<notes>\n"
        f"{notes.strip()}\n"
        "</notes>"
    )


__all__ = [
    "MeetingContext",
    "SYNTHESIS_SYSTEM_PROMPT",
    "CHUNK_SYSTEM_PROMPT",
    "build_synthesis_user_prompt",
    "build_chunk_user_prompt",
    "build_reduce_user_prompt",
]
