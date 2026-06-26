"""Interface en ligne de commande (alternative légère à l'IHM).

Sous-commandes :

* ``devices``           — liste les périphériques de sortie/entrée détectés ;
* ``record``            — enregistre la sortie audio puis produit la synthèse ;
* ``process <fichier>`` — transcrit et synthétise un fichier audio existant ;
* ``gui``               — lance l'interface graphique (comportement par défaut).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Optional

from .config import Config
from .pipeline import MeetingPipeline
from .prompts import MeetingContext


def _progress(message: str) -> None:
    print(f"  … {message}", file=sys.stderr, flush=True)


def _review_synthesis(draft) -> str:
    """Ouvre le brouillon de synthèse dans un éditeur et renvoie le texte relu."""
    import os
    import subprocess
    import tempfile

    editor = os.environ.get("EDITOR") or ("notepad" if os.name == "nt" else "nano")
    fd, tmp = tempfile.mkstemp(suffix=".md", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(draft.synthesis)
        print(f"Relecture : ouverture de l'éditeur ({editor})…", file=sys.stderr)
        try:
            subprocess.call([editor, tmp])
        except Exception:
            input(f"Édite le fichier {tmp} puis appuie sur Entrée…")
        with open(tmp, encoding="utf-8") as handle:
            return handle.read()
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _run(pipeline, draft_factory, review: bool):
    """Génère le brouillon puis finalise (avec relecture éditeur si demandé)."""
    draft = draft_factory()
    synthesis = _review_synthesis(draft) if review else draft.synthesis
    return pipeline.finalize(draft, synthesis, _progress)


def _context_from_args(args) -> MeetingContext:
    participants = [p.strip() for p in (args.participants or "").split(",") if p.strip()]
    return MeetingContext(
        title=args.title,
        participants=participants,
        language=Config.load().language,
    )


# ------------------------------------------------------------------ commandes
def cmd_devices(args) -> int:
    from . import audio

    print("Périphériques de SORTIE capturables (loopback) :")
    loopbacks = audio.list_loopback_devices()
    if not loopbacks:
        print("  (aucun détecté)")
    for d in loopbacks:
        print(f"  - {d.name}\n      id = {d.id}")

    print("\nMicrophones (entrées) :")
    for d in audio.list_input_devices():
        print(f"  - {d.name}\n      id = {d.id}")
    return 0


def cmd_templates(args) -> int:
    from .templates import list_templates

    print("Modèles de synthèse disponibles (option --template) :")
    for key, name in list_templates():
        print(f"  - {key:18s} {name}")
    return 0


def cmd_record(args) -> int:
    from .audio import Recorder

    config = Config.load()
    if args.device:
        config.output_device = args.device
    if args.backend:
        config.backend = args.backend
    if args.docx:
        config.export_docx = True
    if args.pdf:
        config.export_pdf = True
    if args.email:
        config.email_enabled = True
    if args.no_register:
        config.action_register = False
    if args.template:
        config.synthesis_template = args.template
    if args.glossary is not None:
        config.glossary = args.glossary
    if args.context is not None:
        config.context_note = args.context

    recorder = Recorder(
        output_device_id=config.output_device,
        samplerate=config.samplerate,
        include_microphone=args.microphone,
    )
    print("Enregistrement… ", end="", flush=True)
    recorder.start()
    try:
        if args.seconds:
            print(f"(durée fixée à {args.seconds} s)")
            time.sleep(args.seconds)
        else:
            input("Appuie sur Entrée pour arrêter.\n")
    except KeyboardInterrupt:
        pass
    audio, samplerate = recorder.stop()
    print("Arrêté. Traitement en cours…", file=sys.stderr)

    pipeline = MeetingPipeline(config)
    context = _context_from_args(args)
    result = _run(
        pipeline,
        lambda: pipeline.generate_from_recording(audio, samplerate, context, _progress),
        review=args.review,
    )
    _print_result(result)
    return 0


def cmd_process(args) -> int:
    config = Config.load()
    if args.backend:
        config.backend = args.backend
    if args.docx:
        config.export_docx = True
    if args.pdf:
        config.export_pdf = True
    if args.email:
        config.email_enabled = True
    if args.no_register:
        config.action_register = False
    if args.template:
        config.synthesis_template = args.template
    if args.glossary is not None:
        config.glossary = args.glossary
    if args.context is not None:
        config.context_note = args.context
    pipeline = MeetingPipeline(config)
    context = _context_from_args(args)
    result = _run(
        pipeline,
        lambda: pipeline.generate_from_file(Path(args.file), context, _progress),
        review=args.review,
    )
    _print_result(result)
    return 0


def cmd_gui(args) -> int:
    from .gui import run

    run(Config.load())
    return 0


def _print_result(result) -> None:
    print("\n" + "=" * 70)
    print(result.synthesis)
    print("=" * 70)
    print(f"\nSynthèse enregistrée : {result.synthesis_path}", file=sys.stderr)
    if result.docx_path:
        print(f"Document Word        : {result.docx_path}", file=sys.stderr)
    if result.pdf_path:
        print(f"Document PDF         : {result.pdf_path}", file=sys.stderr)
    if result.transcript_path:
        print(f"Transcription        : {result.transcript_path}", file=sys.stderr)
    if result.audio_path:
        print(f"Audio                : {result.audio_path}", file=sys.stderr)
    for path in result.register_paths:
        print(f"Registre d'actions   : {path}", file=sys.stderr)
    if result.email_sent:
        print("E-mail               : envoyé", file=sys.stderr)


# ------------------------------------------------------------------ parseur
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pmo-notes",
        description="Assistant local de prise de notes et de synthèse de réunions.",
    )
    sub = parser.add_subparsers(dest="command")

    p_dev = sub.add_parser("devices", help="Lister les périphériques audio.")
    p_dev.set_defaults(func=cmd_devices)

    p_rec = sub.add_parser("record", help="Enregistrer la sortie audio et synthétiser.")
    p_rec.add_argument("--device", help="Identifiant du périphérique de sortie à capturer.")
    p_rec.add_argument("--seconds", type=float, help="Durée d'enregistrement (sinon : touche Entrée).")
    p_rec.add_argument("--microphone", action="store_true", help="Mixer aussi le micro.")
    p_rec.add_argument("--title", default="Réunion", help="Titre de la réunion.")
    p_rec.add_argument("--participants", default="", help="Participants (séparés par des virgules).")
    p_rec.add_argument("--backend", choices=["ollama", "claude"], help="Forcer le moteur de synthèse.")
    p_rec.add_argument("--docx", action="store_true", help="Exporter aussi en Word (.docx).")
    p_rec.add_argument("--pdf", action="store_true", help="Exporter aussi en PDF.")
    p_rec.add_argument("--email", action="store_true", help="Envoyer la synthèse par e-mail.")
    p_rec.add_argument("--no-register", action="store_true", help="Ne pas mettre à jour le registre d'actions.")
    p_rec.add_argument("--review", action="store_true", help="Relire/éditer la synthèse (éditeur) avant enregistrement.")
    p_rec.add_argument("--template", help="Modèle de synthèse (voir « pmo-notes templates »).")
    p_rec.add_argument("--glossary", help="Glossaire : noms propres/acronymes séparés par des virgules.")
    p_rec.add_argument("--context", help="Note de contexte du projet.")
    p_rec.set_defaults(func=cmd_record)

    p_proc = sub.add_parser("process", help="Synthétiser un fichier audio existant.")
    p_proc.add_argument("file", help="Chemin du fichier audio.")
    p_proc.add_argument("--title", default="Réunion", help="Titre de la réunion.")
    p_proc.add_argument("--participants", default="", help="Participants (séparés par des virgules).")
    p_proc.add_argument("--backend", choices=["ollama", "claude"], help="Forcer le moteur de synthèse.")
    p_proc.add_argument("--docx", action="store_true", help="Exporter aussi en Word (.docx).")
    p_proc.add_argument("--pdf", action="store_true", help="Exporter aussi en PDF.")
    p_proc.add_argument("--email", action="store_true", help="Envoyer la synthèse par e-mail.")
    p_proc.add_argument("--no-register", action="store_true", help="Ne pas mettre à jour le registre d'actions.")
    p_proc.add_argument("--review", action="store_true", help="Relire/éditer la synthèse (éditeur) avant enregistrement.")
    p_proc.add_argument("--template", help="Modèle de synthèse (voir « pmo-notes templates »).")
    p_proc.add_argument("--glossary", help="Glossaire : noms propres/acronymes séparés par des virgules.")
    p_proc.add_argument("--context", help="Note de contexte du projet.")
    p_proc.set_defaults(func=cmd_process)

    p_tpl = sub.add_parser("templates", help="Lister les modèles de synthèse disponibles.")
    p_tpl.set_defaults(func=cmd_templates)

    p_gui = sub.add_parser("gui", help="Lancer l'interface graphique.")
    p_gui.set_defaults(func=cmd_gui)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        # Aucune sous-commande : on lance l'interface graphique.
        return cmd_gui(args)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nInterrompu.", file=sys.stderr)
        return 130
    except Exception as exc:  # message lisible plutôt qu'une trace brute
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
