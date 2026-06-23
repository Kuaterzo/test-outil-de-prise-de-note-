"""Export des synthèses et transcriptions sur le disque."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

_SLUG_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_SLUG_SPACES = re.compile(r"\s+")


def slugify(text: str, max_length: int = 60) -> str:
    """Transforme un titre en composant de nom de fichier sûr (multi-OS)."""
    text = text.strip()
    text = _SLUG_INVALID.sub(" ", text)          # retire les caractères interdits
    text = _SLUG_SPACES.sub("_", text)           # espaces -> underscores
    text = text.strip("._")
    if len(text) > max_length:
        text = text[:max_length].rstrip("._")
    return text or "reunion"


def build_basename(title: str, when: datetime | None = None) -> str:
    """Construit un préfixe de fichier « AAAA-MM-JJ_HHhMM_Titre »."""
    when = when or datetime.now()
    return f"{when:%Y-%m-%d_%Hh%M}_{slugify(title)}"


def save_synthesis(
    synthesis: str,
    output_dir: Path,
    title: str,
    *,
    transcript: str | None = None,
    when: datetime | None = None,
) -> dict[str, Path]:
    """Écrit la synthèse (et éventuellement la transcription) dans `output_dir`.

    Renvoie un dictionnaire des chemins créés, p. ex. ``{"synthesis": ...,
    "transcript": ...}``.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    basename = build_basename(title, when)
    paths: dict[str, Path] = {}

    synthesis_path = output_dir / f"{basename}.md"
    synthesis_path.write_text(_ensure_trailing_newline(synthesis), encoding="utf-8")
    paths["synthesis"] = synthesis_path

    if transcript is not None:
        transcript_path = output_dir / f"{basename}_transcription.txt"
        transcript_path.write_text(_ensure_trailing_newline(transcript), encoding="utf-8")
        paths["transcript"] = transcript_path

    return paths


def _ensure_trailing_newline(text: str) -> str:
    return text if text.endswith("\n") else text + "\n"


__all__ = ["slugify", "build_basename", "save_synthesis"]
