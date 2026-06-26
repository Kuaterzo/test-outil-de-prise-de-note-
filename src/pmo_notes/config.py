"""Configuration de l'application : chargement / sauvegarde en JSON.

La configuration est stockée dans le dossier de données utilisateur
(`%APPDATA%\\PMONotes\\config.json` sous Windows). Des valeurs par défaut
raisonnables permettent à l'outil de fonctionner sans aucune configuration
préalable (transcription locale Whisper + synthèse locale Ollama).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Optional

#: Backends de synthèse disponibles.
BACKENDS = ("ollama", "claude")


def _default_output_dir() -> str:
    """Dossier de sortie par défaut pour les synthèses produites."""
    return str(Path.home() / "Documents" / "Synthèses réunions")


@dataclass
class Config:
    """Paramètres de l'assistant.

    Les champs sont volontairement plats pour faciliter l'édition manuelle
    du fichier JSON et la persistance depuis l'interface graphique.
    """

    # --- Moteur de synthèse -------------------------------------------------
    backend: str = "ollama"  # "ollama" (local) ou "claude" (API)

    # --- Transcription locale (faster-whisper) ------------------------------
    whisper_model: str = "small"          # tiny | base | small | medium | large-v3
    whisper_device: str = "auto"          # auto | cpu | cuda
    whisper_compute_type: str = "auto"    # auto | int8 | int8_float16 | float16 | float32
    language: str = "fr"                  # langue de la réunion (code ISO)

    # --- Backend local Ollama ----------------------------------------------
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    # --- Backend API Claude (Anthropic) ------------------------------------
    claude_model: str = "claude-opus-4-8"
    claude_effort: str = "medium"         # low | medium | high | max

    # --- Diarisation (identification des locuteurs, optionnelle) -----------
    diarization: bool = False             # « qui a dit quoi » via pyannote.audio
    diarization_model: str = "pyannote/speaker-diarization-3.1"
    hf_token: Optional[str] = None        # jeton Hugging Face (sinon variable d'env.)
    infer_speaker_names: bool = True      # deviner les vrais noms (tour de table)

    # --- Capture audio ------------------------------------------------------
    output_device: Optional[str] = None   # id du périphérique « monitor » / loopback choisi
    include_microphone: bool = False      # mixer aussi le micro (expérimental)
    mic_device: Optional[str] = None      # id du micro à mixer
    samplerate: int = 48000               # fréquence d'échantillonnage de capture

    # --- Sortie -------------------------------------------------------------
    output_dir: str = field(default_factory=_default_output_dir)
    save_transcript: bool = True          # enregistrer aussi la transcription brute
    keep_audio: bool = True               # conserver l'enregistrement audio (.wav)
    export_docx: bool = False             # générer aussi une synthèse Word (.docx)
    export_pdf: bool = False              # générer aussi une synthèse PDF
    action_register: bool = True          # tenir un registre d'actions cumulatif (xlsx/csv)
    review_before_save: bool = True       # relire/éditer la synthèse avant diffusion (IHM)

    # --- Envoi par e-mail (optionnel, SMTP) --------------------------------
    email_enabled: bool = False
    email_to: str = ""                    # destinataires, séparés par des virgules
    email_from: str = ""                  # adresse d'expéditeur (sinon smtp_user)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: Optional[str] = None   # de préférence via PMO_SMTP_PASSWORD
    smtp_use_tls: bool = True             # STARTTLS (SSL implicite si port 465)

    # ------------------------------------------------------------------ I/O
    @staticmethod
    def default_path() -> Path:
        """Emplacement standard du fichier de configuration selon l'OS."""
        appdata = os.environ.get("APPDATA")
        if appdata:  # Windows
            base = Path(appdata) / "PMONotes"
        else:  # Linux / macOS
            base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "pmo-notes"
        return base / "config.json"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        """Construit une Config en ignorant les clés inconnues."""
        known = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        """Charge la configuration ; renvoie les valeurs par défaut si absente."""
        path = Path(path) if path else cls.default_path()
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # Fichier corrompu : on repart des valeurs par défaut plutôt que de planter.
            return cls()
        return cls.from_dict(data)

    def save(self, path: Optional[Path] = None) -> Path:
        """Persiste la configuration sur le disque et renvoie le chemin écrit."""
        path = Path(path) if path else self.default_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    # ------------------------------------------------------------- Helpers
    def resolved_output_dir(self) -> Path:
        """Dossier de sortie avec expansion de `~` et des variables d'environnement."""
        return Path(os.path.expandvars(os.path.expanduser(self.output_dir)))

    def validate(self) -> list[str]:
        """Renvoie la liste des problèmes de configuration (vide si tout est correct)."""
        problems: list[str] = []
        if self.backend not in BACKENDS:
            problems.append(
                f"Backend inconnu : « {self.backend} ». Valeurs possibles : {', '.join(BACKENDS)}."
            )
        if self.claude_effort not in ("low", "medium", "high", "max"):
            problems.append(f"Niveau d'effort Claude invalide : « {self.claude_effort} ».")
        if self.samplerate <= 0:
            problems.append("La fréquence d'échantillonnage doit être positive.")
        return problems
