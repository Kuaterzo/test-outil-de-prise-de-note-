#!/usr/bin/env python3
"""Lanceur de l'interface graphique sans installation préalable.

Permet de démarrer l'outil par un simple « python run_gui.py » (ou un
double-clic sous Windows si Python est associé aux fichiers .py), même si le
paquet n'a pas été installé via pip.
"""

import sys
from pathlib import Path

# Rend le paquet importable depuis le dossier src/ sans installation.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from pmo_notes.gui import run  # noqa: E402

if __name__ == "__main__":
    run()
