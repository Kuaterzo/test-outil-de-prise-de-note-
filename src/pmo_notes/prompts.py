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
    glossary: list[str] = field(default_factory=list)  # noms propres, acronymes…
    context_note: str = ""                              # contexte libre du projet

    def participants_line(self) -> str:
        """Représentation lisible des participants, ou « non précisés »."""
        names = [p.strip() for p in self.participants if p.strip()]
        return ", ".join(names) if names else "non précisés"

    def context_block(self) -> str:
        """Bloc « glossaire + contexte » à insérer dans l'invite (vide si aucun)."""
        pieces: list[str] = []
        terms = [t.strip() for t in self.glossary if t.strip()]
        if terms:
            pieces.append(
                "Glossaire (noms propres et acronymes à orthographier correctement) : "
                + ", ".join(terms)
                + "."
            )
        note = (self.context_note or "").strip()
        if note:
            pieces.append("Contexte du projet : " + note)
        return "\n".join(pieces)


# Persona + consignes de rédaction. Volontairement strict sur la fidélité au
# contenu : l'outil doit synthétiser, pas inventer.
SYNTHESIS_SYSTEM_PROMPT = """\
Tu es l'assistant d'un PMO (Project Management Officer) chargé de rédiger la \
synthèse écrite d'une réunion à partir de sa transcription audio.

La transcription est issue d'une reconnaissance vocale automatique : elle peut \
contenir des erreurs, des hésitations, des répétitions ou une ponctuation \
approximative. Reconstitue le sens sans inventer d'informations absentes.

Si la transcription comporte des étiquettes de locuteurs (par exemple \
« Locuteur 1 : … »), exploite-les pour attribuer correctement les propos et les \
actions aux bonnes personnes, sans inventer de noms.

Si un glossaire ou un contexte de projet est fourni, respecte l'orthographe des \
noms propres et acronymes indiqués et emploie la terminologie du projet.

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
    block = context.context_block()
    context_part = f"{block}\n\n" if block else ""
    return (
        f"Titre de la réunion : {context.title}\n"
        f"Date : {context.date}\n"
        f"Participants : {context.participants_line()}\n\n"
        f"{context_part}"
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
    block = context.context_block()
    context_part = f"{block}\n\n" if block else ""
    return (
        f"Titre de la réunion : {context.title}\n"
        f"Date : {context.date}\n"
        f"Participants : {context.participants_line()}\n\n"
        f"{context_part}"
        "Voici les notes prises sur les différentes portions de la réunion, dans "
        "l'ordre chronologique. Rédige la synthèse finale en respectant la "
        "structure imposée.\n\n"
        "<notes>\n"
        f"{notes.strip()}\n"
        "</notes>"
    )


# --- Identification des noms de locuteurs (à partir du tour de table) -------
# Lorsque la diarisation a étiqueté les interventions « Locuteur 1/2/… », on
# tente de retrouver les vrais noms à partir des présentations énoncées dans la
# réunion. La sortie est un JSON strict, facile à parser et à appliquer.

SPEAKER_NAMES_SYSTEM_PROMPT = """\
Tu analyses la transcription d'une réunion où les interventions sont étiquetées \
« Locuteur 1 », « Locuteur 2 », etc. À partir des présentations (tour de table) \
et du contexte, identifie le prénom ou le nom réel de chaque locuteur LORSQU'IL \
est clairement énoncé dans la transcription.

Réponds UNIQUEMENT par un objet JSON associant chaque étiquette à un nom, par \
exemple : {"Locuteur 1": "Alice Martin", "Locuteur 2": "Bob"}.

Règles impératives :
- N'inclus une étiquette QUE si le nom est explicite et non ambigu.
- N'invente jamais de nom. En cas de doute, omets simplement l'étiquette.
- Ne renvoie rien d'autre que l'objet JSON (pas de phrase, pas de balises).
"""


def build_speaker_names_user_prompt(labeled_transcript: str) -> str:
    """Invite pour déduire les noms des locuteurs d'une transcription étiquetée."""
    return (
        "Transcription étiquetée par locuteur :\n\n"
        "<transcription>\n"
        f"{labeled_transcript.strip()}\n"
        "</transcription>"
    )


__all__ = [
    "MeetingContext",
    "SYNTHESIS_SYSTEM_PROMPT",
    "CHUNK_SYSTEM_PROMPT",
    "SPEAKER_NAMES_SYSTEM_PROMPT",
    "build_synthesis_user_prompt",
    "build_chunk_user_prompt",
    "build_reduce_user_prompt",
    "build_speaker_names_user_prompt",
]
