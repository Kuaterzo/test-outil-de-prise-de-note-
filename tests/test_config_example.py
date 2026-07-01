"""Garde-fou : le fichier d'exemple doit rester aligné sur la classe Config."""

import dataclasses
import json
from pathlib import Path

from pmo_notes.config import Config

_EXAMPLE = Path(__file__).resolve().parents[1] / "config.example.json"


def _example() -> dict:
    return json.loads(_EXAMPLE.read_text(encoding="utf-8"))


def test_example_keys_match_config_fields():
    example_keys = set(_example().keys())
    config_fields = {f.name for f in dataclasses.fields(Config)}
    assert example_keys == config_fields, (
        f"Manquants dans l'exemple : {config_fields - example_keys} ; "
        f"en trop : {example_keys - config_fields}"
    )


def test_example_loads_and_validates():
    cfg = Config.from_dict(_example())
    assert cfg.validate() == []
