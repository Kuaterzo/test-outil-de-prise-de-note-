"""Modèles de synthèse par type de réunion.

Chaque modèle définit la **structure de sections** de la synthèse (COPIL,
atelier, rétrospective, point d'avancement…). Le persona, les consignes de
fidélité et la note sur les étiquettes de locuteurs restent partagés : seules
les sections changent. Le modèle « standard » réutilise l'invite historique à
l'identique.

Des modèles personnalisés peuvent être ajoutés dans un fichier `templates.json`
placé à côté de la configuration (voir :func:`load_custom_templates`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from .prompts import SYNTHESIS_SYSTEM_PROMPT

# Préambule et règles partagés par tous les modèles générés.
_PREAMBLE = """\
Tu es l'assistant d'un PMO (Project Management Officer) chargé de rédiger la \
synthèse écrite d'une réunion à partir de sa transcription audio.

La transcription est issue d'une reconnaissance vocale automatique : elle peut \
contenir des erreurs, des hésitations ou une ponctuation approximative. \
Reconstitue le sens sans inventer d'informations absentes.

Si la transcription comporte des étiquettes de locuteurs (« Locuteur 1 : … » ou \
des noms), exploite-les pour attribuer correctement les propos et les actions \
aux bonnes personnes, sans inventer de noms.

Si un glossaire ou un contexte de projet est fourni, respecte l'orthographe des \
noms propres et acronymes indiqués et emploie la terminologie du projet.

Rédige une synthèse professionnelle, claire et concise, en français, au format \
Markdown, en respectant EXACTEMENT la structure de sections suivante :"""

_POSTAMBLE = """\
Règles impératives :
- N'invente jamais de noms, de chiffres, de dates ou d'engagements absents de la \
transcription.
- Si une information est ambiguë ou inaudible, signale-la avec « [à confirmer] ».
- Ne commente pas ton propre travail : produis uniquement la synthèse.
- Conserve les titres de sections ci-dessus à l'identique."""

# Consigne commune pour la section des actions (format exploité par le registre).
_ACTIONS_INSTRUCTION = (
    "Liste des actions décidées. Pour CHAQUE action, précise la personne "
    "concernée (le responsable) et l'échéance lorsqu'elle est mentionnée, au "
    "format : « **Responsable** — action à mener (échéance) ». Si le responsable "
    "ou l'échéance n'est pas explicite, indique « responsable à confirmer » ou "
    "« échéance à confirmer » plutôt que de l'inventer."
)


@dataclass
class SynthesisTemplate:
    """Un modèle de synthèse : un ensemble ordonné de sections."""

    key: str
    name: str
    sections: list[tuple[str, str]] = field(default_factory=list)
    #: Si renseigné, ce texte est utilisé tel quel (cas du modèle « standard »).
    system_prompt_override: Optional[str] = None

    def to_system_prompt(self) -> str:
        """Compose l'invite système correspondant au modèle."""
        if self.system_prompt_override is not None:
            return self.system_prompt_override
        body = "\n\n".join(f"## {title}\n{instruction}" for title, instruction in self.sections)
        return f"{_PREAMBLE}\n\n{body}\n\n{_POSTAMBLE}"


# --------------------------------------------------------------- modèles fournis
BUILTIN_TEMPLATES: dict[str, SynthesisTemplate] = {
    "standard": SynthesisTemplate(
        key="standard",
        name="Standard",
        system_prompt_override=SYNTHESIS_SYSTEM_PROMPT,
    ),
    "copil": SynthesisTemplate(
        key="copil",
        name="Comité de pilotage (COPIL)",
        sections=[
            ("Introduction", "Contexte du comité : objet, périmètre du projet, participants si identifiables. 2 à 4 phrases."),
            ("Avancement et points clés", "Synthèse de l'avancement présenté et des points clés, par thème (puces ou courts paragraphes)."),
            ("Risques et points de vigilance", "Risques, alertes et points de vigilance évoqués, avec leur niveau d'importance si mentionné."),
            ("Décisions prises", "Décisions arrêtées pendant le comité, formulées clairement."),
            ("Actions et responsables", _ACTIONS_INSTRUCTION),
            ("Conclusion et prochains jalons", "Bilan, prochaines échéances et jalons à venir. 2 à 4 phrases."),
        ],
    ),
    "atelier": SynthesisTemplate(
        key="atelier",
        name="Atelier de travail",
        sections=[
            ("Introduction", "Objectif de l'atelier et participants si identifiables. 2 à 3 phrases."),
            ("Points discutés", "Synthèse des sujets travaillés et des idées échangées (puces)."),
            ("Livrables et productions", "Livrables, productions ou conclusions issus de l'atelier."),
            ("Actions à mener", _ACTIONS_INSTRUCTION),
            ("Conclusion", "Bilan et suites envisagées. 2 à 3 phrases."),
        ],
    ),
    "retrospective": SynthesisTemplate(
        key="retrospective",
        name="Rétrospective",
        sections=[
            ("Introduction", "Cadre de la rétrospective (période, équipe) si identifiable. 1 à 2 phrases."),
            ("Ce qui a bien fonctionné", "Points positifs et réussites mis en avant (puces)."),
            ("Points à améliorer", "Difficultés, irritants et axes d'amélioration évoqués (puces)."),
            ("Actions d'amélioration", _ACTIONS_INSTRUCTION),
            ("Conclusion", "Synthèse des enseignements et engagements pour la suite."),
        ],
    ),
    "point_avancement": SynthesisTemplate(
        key="point_avancement",
        name="Point d'avancement / Daily",
        sections=[
            ("Introduction", "Cadre du point (équipe, périmètre) si identifiable. 1 à 2 phrases."),
            ("Avancement depuis le dernier point", "Ce qui a progressé depuis la dernière réunion (puces)."),
            ("Blocages et difficultés", "Points de blocage, dépendances et difficultés signalés."),
            ("Actions et prochaines étapes", _ACTIONS_INSTRUCTION),
            ("Conclusion", "Synthèse et priorités jusqu'au prochain point. 1 à 2 phrases."),
        ],
    ),
}


# --------------------------------------------------------------- chargement
def load_custom_templates(path=None) -> dict[str, SynthesisTemplate]:
    """Charge d'éventuels modèles personnalisés depuis `templates.json`.

    Format attendu : un objet JSON associant une clé à
    ``{"name": "...", "sections": [["Titre", "Consigne"], ...]}``.
    """
    from pathlib import Path

    from .config import Config

    path = Path(path) if path else Config.default_path().parent / "templates.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

    templates: dict[str, SynthesisTemplate] = {}
    for key, spec in (data or {}).items():
        if not isinstance(spec, dict):
            continue
        name = spec.get("name", key)
        raw_sections = spec.get("sections", [])
        sections = [
            (str(s[0]), str(s[1]))
            for s in raw_sections
            if isinstance(s, (list, tuple)) and len(s) == 2
        ]
        if sections:
            templates[str(key)] = SynthesisTemplate(key=str(key), name=str(name), sections=sections)
    return templates


def load_templates(custom_path=None) -> dict[str, SynthesisTemplate]:
    """Renvoie les modèles fournis, complétés/écrasés par les personnalisés."""
    templates = dict(BUILTIN_TEMPLATES)
    templates.update(load_custom_templates(custom_path))
    return templates


def get_template(key: str, templates: Optional[dict] = None) -> SynthesisTemplate:
    """Renvoie le modèle demandé, ou le modèle « standard » par défaut."""
    templates = templates if templates is not None else load_templates()
    return templates.get(key) or templates.get("standard") or BUILTIN_TEMPLATES["standard"]


def list_templates(templates: Optional[dict] = None) -> list[tuple[str, str]]:
    """Liste ``(clé, nom)`` des modèles disponibles, « standard » en tête."""
    templates = templates if templates is not None else load_templates()
    ordered = ["standard", "copil", "atelier", "retrospective", "point_avancement"]
    pairs = [(k, templates[k].name) for k in ordered if k in templates]
    for key, tpl in templates.items():  # modèles personnalisés éventuels
        if key not in ordered:
            pairs.append((key, tpl.name))
    return pairs


__all__ = [
    "SynthesisTemplate",
    "BUILTIN_TEMPLATES",
    "load_custom_templates",
    "load_templates",
    "get_template",
    "list_templates",
]
