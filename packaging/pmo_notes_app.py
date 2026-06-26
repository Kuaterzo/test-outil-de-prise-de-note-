"""Point d'entrée de l'exécutable Windows (cible PyInstaller).

Le `.spec` ajoute `src/` au `pathex`, ce qui rend `pmo_notes` importable sans
manipuler `sys.path` ici.
"""

from pmo_notes.gui import run

if __name__ == "__main__":
    run()
