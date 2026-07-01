# -*- mode: python ; coding: utf-8 -*-
"""Spécification PyInstaller pour l'assistant de synthèse de réunions.

Construction (sous Windows, depuis la racine du projet) :

    pip install -r requirements.txt pyinstaller
    pyinstaller packaging/pmo-notes.spec --noconfirm

Le résultat est un dossier autonome « dist/PMONotes/ » contenant « PMONotes.exe ».
On privilégie le mode « onedir » (un dossier) plutôt que « onefile » : il démarre
plus vite et s'avère bien plus fiable avec les bibliothèques natives lourdes
(ctranslate2, onnxruntime, PyAV…).

Note : le modèle Whisper est téléchargé au premier lancement (connexion requise
une fois), puis mis en cache localement — il n'est volontairement pas embarqué.
"""

import os

from PyInstaller.utils.hooks import collect_all

# Paquets nécessitant la collecte de leurs données/binaires/sous-modules.
_PACKAGES = [
    "faster_whisper",   # transcription (+ assets VAD)
    "ctranslate2",      # moteur d'inférence de Whisper (binaires natifs)
    "av",               # PyAV : décodage audio
    "tokenizers",
    "onnxruntime",      # VAD silero
    "huggingface_hub",
    "soundcard",        # capture audio (loopback)
    "anthropic",        # backend de synthèse API Claude
    "reportlab",        # export PDF
    "docx",             # python-docx : export Word
]

datas, binaries, hiddenimports = [], [], []
for _pkg in _PACKAGES:
    try:
        _d, _b, _h = collect_all(_pkg)
        datas += _d
        binaries += _b
        hiddenimports += _h
    except Exception as exc:  # un paquet optionnel peut être absent à la construction
        print(f"[pmo-notes.spec] collecte ignorée pour {_pkg} : {exc}")

# `pyannote.audio` (diarisation) est optionnel : on le collecte s'il est présent.
try:
    _d, _b, _h = collect_all("pyannote.audio")
    datas += _d
    binaries += _b
    hiddenimports += _h
except Exception:
    pass

src_path = os.path.join(SPECPATH, "..", "src")  # noqa: F821 (SPECPATH fourni par PyInstaller)

a = Analysis(  # noqa: F821
    [os.path.join(SPECPATH, "pmo_notes_app.py")],  # noqa: F821
    pathex=[src_path],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PMONotes",
    console=False,          # application fenêtrée (pas de console)
    disable_windowed_traceback=False,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    name="PMONotes",
)
