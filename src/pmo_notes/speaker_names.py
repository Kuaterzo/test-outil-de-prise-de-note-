"""Détection des noms réels des locuteurs à partir d'une transcription étiquetée.

Après la diarisation, les interventions sont préfixées « Locuteur 1 : … ». Ce
module demande au moteur de synthèse de déduire les vrais noms (énoncés lors du
tour de table) puis réétiquette la transcription en conséquence.

La logique de parsing du JSON et de remplacement est *pure* (sans dépendance) et
testable ; l'appel au modèle est délégué à un :class:`~pmo_notes.summarization.base.Summarizer`.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from .prompts import SPEAKER_NAMES_SYSTEM_PROMPT, build_speaker_names_user_prompt

if TYPE_CHECKING:
    from .summarization.base import Summarizer

_LABEL_RE = re.compile(r"^Locuteur\s+\d+$")


def parse_name_mapping(raw: str) -> dict[str, str]:
    """Extrait un mapping {« Locuteur N » : nom} d'une réponse de modèle.

    Tolère un éventuel texte autour du JSON (on isole le premier objet `{…}`).
    Ne conserve que les clés de la forme « Locuteur N » associées à un nom non
    vide, afin d'éviter d'injecter des valeurs parasites.
    """
    if not raw:
        return {}
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end < start:
        return {}
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}

    mapping: dict[str, str] = {}
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        label = key.strip()
        name = value.strip()
        if name and _LABEL_RE.match(label):
            mapping[label] = name
    return mapping


def apply_speaker_names(transcript: str, mapping: dict[str, str]) -> str:
    """Remplace les étiquettes « Locuteur N » par les noms fournis.

    Le remplacement traite les étiquettes les plus longues d'abord pour éviter
    qu'« Locuteur 1 » ne soit confondu avec « Locuteur 10 ».
    """
    if not mapping:
        return transcript
    result = transcript
    for label in sorted(mapping, key=len, reverse=True):
        result = re.sub(rf"\b{re.escape(label)}\b", mapping[label], result)
    return result


def infer_speaker_names(summarizer: "Summarizer", labeled_transcript: str) -> dict[str, str]:
    """Interroge le modèle pour déduire les noms des locuteurs."""
    raw = summarizer.complete(
        SPEAKER_NAMES_SYSTEM_PROMPT,
        build_speaker_names_user_prompt(labeled_transcript),
    )
    return parse_name_mapping(raw)


def name_speakers(summarizer: "Summarizer", labeled_transcript: str) -> tuple[str, dict[str, str]]:
    """Déduit les noms puis renvoie ``(transcription_renommée, mapping)``."""
    mapping = infer_speaker_names(summarizer, labeled_transcript)
    return apply_speaker_names(labeled_transcript, mapping), mapping


__all__ = [
    "parse_name_mapping",
    "apply_speaker_names",
    "infer_speaker_names",
    "name_speakers",
]
