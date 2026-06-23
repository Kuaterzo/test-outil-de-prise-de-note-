"""Point d'entrée : ``python -m pmo_notes`` (IHM par défaut, ou sous-commandes CLI)."""

from __future__ import annotations

import sys


def main() -> int:
    from .cli import main as cli_main

    return cli_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
