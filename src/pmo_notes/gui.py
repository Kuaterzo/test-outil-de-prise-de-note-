"""Interface graphique (Tkinter) de l'assistant de synthèse de réunions.

Pilotage simple : on choisit la sortie audio à capturer et le moteur de
synthèse, on clique sur « Démarrer », puis « Arrêter » à la fin de la réunion.
L'outil transcrit localement, synthétise, et affiche/enregistre le résultat.

La capture audio tourne dans des threads dédiés (voir :mod:`audio`) ; la
transcription et la synthèse, potentiellement longues, tournent dans un thread
de travail dont les messages remontent à l'IHM via une file d'attente.
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from .config import Config
from .pipeline import MeetingPipeline
from .prompts import MeetingContext

_POLL_MS = 120  # fréquence de rafraîchissement de l'IHM pendant les traitements


class App:
    """Fenêtre principale de l'application."""

    def __init__(self, root: tk.Tk, config: Optional[Config] = None) -> None:
        self.root = root
        self.config = config or Config.load()
        self.pipeline = MeetingPipeline(self.config)

        self._recorder = None
        self._devices = []  # liste d'AudioDevice du combobox
        self._record_start: Optional[datetime] = None
        self._messages: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self._busy = False  # transcription/synthèse en cours

        root.title("Assistant de synthèse de réunions — PMO")
        root.minsize(760, 640)
        self._build_ui()
        self._apply_config()
        self.refresh_devices()
        self._poll_messages()
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)

        # --- Métadonnées de la réunion ---
        meta = ttk.LabelFrame(main, text="Réunion", padding=8)
        meta.grid(row=0, column=0, sticky="ew", **pad)
        meta.columnconfigure(1, weight=1)
        ttk.Label(meta, text="Titre :").grid(row=0, column=0, sticky="w")
        self.title_var = tk.StringVar(value="Réunion")
        ttk.Entry(meta, textvariable=self.title_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Label(meta, text="Participants :").grid(row=1, column=0, sticky="w")
        self.participants_var = tk.StringVar()
        ttk.Entry(meta, textvariable=self.participants_var).grid(row=1, column=1, sticky="ew", padx=6)
        ttk.Label(meta, text="(séparés par des virgules)", foreground="#666").grid(
            row=2, column=1, sticky="w", padx=6
        )

        # --- Capture audio ---
        audio = ttk.LabelFrame(main, text="Sortie audio à capturer", padding=8)
        audio.grid(row=1, column=0, sticky="ew", **pad)
        audio.columnconfigure(0, weight=1)
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(audio, textvariable=self.device_var, state="readonly")
        self.device_combo.grid(row=0, column=0, sticky="ew")
        ttk.Button(audio, text="Rafraîchir", command=self.refresh_devices).grid(
            row=0, column=1, padx=6
        )
        self.mic_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            audio,
            text="Mixer aussi mon microphone (capture ma voix — expérimental)",
            variable=self.mic_var,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # --- Moteur de synthèse ---
        engine = ttk.LabelFrame(main, text="Moteur de synthèse", padding=8)
        engine.grid(row=2, column=0, sticky="ew", **pad)
        engine.columnconfigure(0, weight=1)
        self.backend_var = tk.StringVar(value="ollama")
        row = ttk.Frame(engine)
        row.grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(
            row, text="Local (Ollama)", value="ollama",
            variable=self.backend_var, command=self._on_backend_change,
        ).pack(side="left")
        ttk.Radiobutton(
            row, text="API Claude (Anthropic)", value="claude",
            variable=self.backend_var, command=self._on_backend_change,
        ).pack(side="left", padx=12)

        # Sous-cadre Ollama
        self.ollama_frame = ttk.Frame(engine)
        self.ollama_frame.columnconfigure(1, weight=1)
        ttk.Label(self.ollama_frame, text="Serveur :").grid(row=0, column=0, sticky="w")
        self.ollama_host_var = tk.StringVar()
        ttk.Entry(self.ollama_frame, textvariable=self.ollama_host_var).grid(
            row=0, column=1, sticky="ew", padx=6
        )
        ttk.Label(self.ollama_frame, text="Modèle :").grid(row=1, column=0, sticky="w")
        self.ollama_model_var = tk.StringVar()
        ttk.Entry(self.ollama_frame, textvariable=self.ollama_model_var).grid(
            row=1, column=1, sticky="ew", padx=6
        )

        # Sous-cadre Claude
        self.claude_frame = ttk.Frame(engine)
        self.claude_frame.columnconfigure(1, weight=1)
        ttk.Label(self.claude_frame, text="Modèle :").grid(row=0, column=0, sticky="w")
        self.claude_model_var = tk.StringVar()
        ttk.Entry(self.claude_frame, textvariable=self.claude_model_var).grid(
            row=0, column=1, sticky="ew", padx=6
        )
        ttk.Label(self.claude_frame, text="Effort :").grid(row=1, column=0, sticky="w")
        self.claude_effort_var = tk.StringVar()
        ttk.Combobox(
            self.claude_frame, textvariable=self.claude_effort_var, state="readonly",
            values=["low", "medium", "high", "max"], width=10,
        ).grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(
            self.claude_frame,
            text="Nécessite la variable d'environnement ANTHROPIC_API_KEY.",
            foreground="#666",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 0))

        # --- Modèle de transcription ---
        trans = ttk.LabelFrame(main, text="Transcription (Whisper, local)", padding=8)
        trans.grid(row=3, column=0, sticky="ew", **pad)
        ttk.Label(trans, text="Modèle :").grid(row=0, column=0, sticky="w")
        self.whisper_model_var = tk.StringVar()
        ttk.Combobox(
            trans, textvariable=self.whisper_model_var, state="readonly", width=12,
            values=["tiny", "base", "small", "medium", "large-v3"],
        ).grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(
            trans, text="(« small » : bon compromis ; « medium » : plus précis, plus lent)",
            foreground="#666",
        ).grid(row=0, column=2, sticky="w")
        self.diar_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            trans,
            text="Identifier les locuteurs (diarisation — nécessite pyannote.audio + jeton Hugging Face)",
            variable=self.diar_var,
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))

        # --- Formats d'export ---
        export = ttk.LabelFrame(main, text="Formats d'export", padding=8)
        export.grid(row=4, column=0, sticky="ew", **pad)
        ttk.Label(export, text="Markdown (.md) toujours généré.", foreground="#666").pack(
            side="left"
        )
        self.docx_var = tk.BooleanVar(value=False)
        self.pdf_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(export, text="Word (.docx)", variable=self.docx_var).pack(
            side="left", padx=12
        )
        ttk.Checkbutton(export, text="PDF (.pdf)", variable=self.pdf_var).pack(side="left")

        # --- Contrôles ---
        controls = ttk.Frame(main)
        controls.grid(row=5, column=0, sticky="ew", **pad)
        self.start_btn = ttk.Button(controls, text="● Démarrer", command=self.start_recording)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(
            controls, text="■ Arrêter", command=self.stop_recording, state="disabled"
        )
        self.stop_btn.pack(side="left", padx=6)
        self.file_btn = ttk.Button(
            controls, text="Charger un fichier audio…", command=self.load_audio_file
        )
        self.file_btn.pack(side="left", padx=6)
        self.timer_var = tk.StringVar(value="00:00")
        ttk.Label(controls, textvariable=self.timer_var, font=("TkDefaultFont", 12, "bold")).pack(
            side="right"
        )
        self.level_bar = ttk.Progressbar(controls, length=120, maximum=100)
        self.level_bar.pack(side="right", padx=8)

        # --- Statut ---
        self.status_var = tk.StringVar(value="Prêt.")
        self.status_label = ttk.Label(main, textvariable=self.status_var, foreground="#0a6")
        self.status_label.grid(row=6, column=0, sticky="w", **pad)

        # --- Synthèse ---
        out = ttk.LabelFrame(main, text="Synthèse", padding=8)
        out.grid(row=7, column=0, sticky="nsew", **pad)
        main.rowconfigure(7, weight=1)
        out.columnconfigure(0, weight=1)
        out.rowconfigure(0, weight=1)
        self.output = ScrolledText(out, wrap="word", height=14, font=("TkDefaultFont", 10))
        self.output.grid(row=0, column=0, sticky="nsew")
        bottom = ttk.Frame(out)
        bottom.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.open_btn = ttk.Button(
            bottom, text="Ouvrir le dossier des synthèses",
            command=self.open_output_dir, state="disabled",
        )
        self.open_btn.pack(side="left")
        self.saved_var = tk.StringVar()
        ttk.Label(bottom, textvariable=self.saved_var, foreground="#666").pack(
            side="left", padx=10
        )

    # -------------------------------------------------------------- config I/O
    def _apply_config(self) -> None:
        c = self.config
        self.backend_var.set(c.backend)
        self.mic_var.set(c.include_microphone)
        self.ollama_host_var.set(c.ollama_host)
        self.ollama_model_var.set(c.ollama_model)
        self.claude_model_var.set(c.claude_model)
        self.claude_effort_var.set(c.claude_effort)
        self.whisper_model_var.set(c.whisper_model)
        self.diar_var.set(c.diarization)
        self.docx_var.set(c.export_docx)
        self.pdf_var.set(c.export_pdf)
        self._on_backend_change()

    def _collect_config(self) -> None:
        c = self.config
        c.backend = self.backend_var.get()
        c.include_microphone = bool(self.mic_var.get())
        c.ollama_host = self.ollama_host_var.get().strip() or c.ollama_host
        c.ollama_model = self.ollama_model_var.get().strip() or c.ollama_model
        c.claude_model = self.claude_model_var.get().strip() or c.claude_model
        c.claude_effort = self.claude_effort_var.get() or c.claude_effort
        c.whisper_model = self.whisper_model_var.get() or c.whisper_model
        c.diarization = bool(self.diar_var.get())
        c.export_docx = bool(self.docx_var.get())
        c.export_pdf = bool(self.pdf_var.get())
        device = self._selected_device()
        c.output_device = device.id if device else c.output_device
        try:
            c.save()
        except OSError:
            pass  # la persistance ne doit jamais bloquer l'utilisateur

    def _on_backend_change(self) -> None:
        if self.backend_var.get() == "claude":
            self.ollama_frame.grid_forget()
            self.claude_frame.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        else:
            self.claude_frame.grid_forget()
            self.ollama_frame.grid(row=1, column=0, sticky="ew", pady=(6, 0))

    # --------------------------------------------------------------- devices
    def refresh_devices(self) -> None:
        """(Re)charge la liste des périphériques de sortie capturables."""
        try:
            from . import audio

            self._devices = audio.list_loopback_devices()
        except Exception as exc:  # soundcard absent / erreur pilote
            self._devices = []
            self.device_combo["values"] = []
            self.set_status(f"Capture audio indisponible : {exc}", error=True)
            return

        names = [d.name for d in self._devices]
        self.device_combo["values"] = names
        if not names:
            self.set_status(
                "Aucun périphérique de sortie détecté. Branche/active un périphérique "
                "puis rafraîchis.",
                error=True,
            )
            return

        # Restaure la sélection mémorisée si possible.
        selected_index = 0
        if self.config.output_device:
            for i, d in enumerate(self._devices):
                if d.id == self.config.output_device:
                    selected_index = i
                    break
        self.device_combo.current(selected_index)
        self.set_status("Prêt.")

    def _selected_device(self):
        idx = self.device_combo.current()
        if 0 <= idx < len(self._devices):
            return self._devices[idx]
        return None

    # --------------------------------------------------------------- recording
    def start_recording(self) -> None:
        if self._busy:
            return
        device = self._selected_device()
        if device is None:
            messagebox.showwarning(
                "Périphérique manquant",
                "Sélectionne d'abord la sortie audio à capturer.",
            )
            return
        self._collect_config()

        try:
            from .audio import Recorder

            self._recorder = Recorder(
                output_device_id=device.id,
                samplerate=self.config.samplerate,
                include_microphone=self.config.include_microphone,
            )
            self._recorder.start()
        except Exception as exc:
            messagebox.showerror("Erreur de capture", str(exc))
            self._recorder = None
            return

        self._record_start = datetime.now()
        self.start_btn["state"] = "disabled"
        self.file_btn["state"] = "disabled"
        self.stop_btn["state"] = "normal"
        self.saved_var.set("")
        self.set_status("Enregistrement en cours…")
        self._tick_recording()

    def _tick_recording(self) -> None:
        if not (self._recorder and self._recorder.is_recording):
            return
        elapsed = datetime.now() - self._record_start
        total = int(elapsed.total_seconds())
        self.timer_var.set(f"{total // 60:02d}:{total % 60:02d}")
        self.level_bar["value"] = min(100, self._recorder.level * 400)
        self.root.after(200, self._tick_recording)

    def stop_recording(self) -> None:
        if not self._recorder:
            return
        self.stop_btn["state"] = "disabled"
        try:
            audio, samplerate = self._recorder.stop()
        except Exception as exc:
            messagebox.showerror("Erreur de capture", str(exc))
            self._reset_idle()
            return
        finally:
            self._recorder = None
        self.level_bar["value"] = 0
        self._start_processing(audio=audio, samplerate=samplerate)

    # --------------------------------------------------------------- file mode
    def load_audio_file(self) -> None:
        if self._busy:
            return
        path = filedialog.askopenfilename(
            title="Choisir un fichier audio",
            filetypes=[
                ("Fichiers audio", "*.wav *.mp3 *.m4a *.flac *.ogg *.aac *.wma"),
                ("Tous les fichiers", "*.*"),
            ],
        )
        if not path:
            return
        self._collect_config()
        self._start_processing(audio_path=Path(path))

    # --------------------------------------------------------------- processing
    def _start_processing(self, *, audio=None, samplerate=None, audio_path=None) -> None:
        self._busy = True
        self._set_controls_enabled(False)
        self.output.delete("1.0", "end")
        context = self._build_context()
        worker = threading.Thread(
            target=self._process_worker,
            args=(context, audio, samplerate, audio_path),
            daemon=True,
        )
        worker.start()

    def _process_worker(self, context, audio, samplerate, audio_path) -> None:
        def progress(msg: str) -> None:
            self._messages.put(("status", msg))

        try:
            if audio_path is not None:
                result = self.pipeline.process_audio_file(audio_path, context, progress)
            else:
                result = self.pipeline.process_recording(
                    audio, samplerate, context, progress
                )
            self._messages.put(("result", result))
        except Exception as exc:  # remonte toute erreur à l'IHM
            self._messages.put(("error", str(exc)))

    def _poll_messages(self) -> None:
        """Vide la file des messages venant du thread de travail (boucle IHM)."""
        try:
            while True:
                kind, payload = self._messages.get_nowait()
                if kind == "status":
                    self.set_status(str(payload))
                elif kind == "result":
                    self._on_result(payload)
                elif kind == "error":
                    self._on_error(str(payload))
        except queue.Empty:
            pass
        self.root.after(_POLL_MS, self._poll_messages)

    def _on_result(self, result) -> None:
        self.output.delete("1.0", "end")
        self.output.insert("1.0", result.synthesis)
        files = ", ".join(p.name for p in result.all_paths())
        self.saved_var.set(f"Fichiers enregistrés : {files}")
        self.open_btn["state"] = "normal"
        self.set_status("Synthèse terminée. ✔")
        self._busy = False
        self._reset_idle()

    def _on_error(self, message: str) -> None:
        self.set_status(f"Erreur : {message}", error=True)
        messagebox.showerror("Erreur", message)
        self._busy = False
        self._reset_idle()

    # --------------------------------------------------------------- helpers
    def _build_context(self) -> MeetingContext:
        participants = [
            p.strip() for p in self.participants_var.get().split(",") if p.strip()
        ]
        return MeetingContext(
            title=self.title_var.get().strip() or "Réunion",
            date=datetime.now().date().isoformat(),
            participants=participants,
            language=self.config.language,
        )

    def _set_controls_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.start_btn["state"] = state
        self.file_btn["state"] = state

    def _reset_idle(self) -> None:
        self.timer_var.set("00:00")
        self._set_controls_enabled(True)
        self.stop_btn["state"] = "disabled"

    def set_status(self, message: str, *, error: bool = False) -> None:
        self.status_var.set(message)
        self.status_label.configure(foreground="#c00" if error else "#0a6")

    def open_output_dir(self) -> None:
        path = self.config.resolved_output_dir()
        path.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception:
            # Repli universel : ouvre via le navigateur de fichiers du système.
            webbrowser.open(path.as_uri())

    def _on_close(self) -> None:
        try:
            if self._recorder and self._recorder.is_recording:
                self._recorder.stop()
        except Exception:
            pass
        self._collect_config()
        self.root.destroy()


def run(config: Optional[Config] = None) -> None:
    """Lance l'interface graphique."""
    root = tk.Tk()
    App(root, config)
    root.mainloop()


__all__ = ["App", "run"]
