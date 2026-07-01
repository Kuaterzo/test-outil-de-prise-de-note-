"""Vue interactive du registre d'actions (fenêtre Tkinter).

Affiche le registre cumulatif sous forme de tableau, permet de **filtrer** par
responsable et par statut, de **changer le statut** des actions sélectionnées
(« Fait », « En cours », …) et d'**enregistrer** les modifications dans le
registre (CSV + Excel).

Ce module n'est importé qu'au moment d'ouvrir la fenêtre (il dépend de Tkinter).
La logique de lecture/écriture/filtre vit dans :mod:`pmo_notes.action_register`
et est testée indépendamment.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .action_register import (
    STATUSES,
    filter_items,
    read_register,
    write_register,
)

_COLUMNS = ("date", "reunion", "responsable", "action", "echeance", "statut")
_HEADINGS = {
    "date": "Date",
    "reunion": "Réunion",
    "responsable": "Responsable",
    "action": "Action",
    "echeance": "Échéance",
    "statut": "Statut",
}
_WIDTHS = {
    "date": 80,
    "reunion": 130,
    "responsable": 110,
    "action": 360,
    "echeance": 90,
    "statut": 90,
}


def open_register(parent, config) -> None:
    """Ouvre la fenêtre du registre, ou informe si aucune action n'existe."""
    items = read_register(config.resolved_output_dir())
    if not items:
        messagebox.showinfo(
            "Registre d'actions",
            "Aucune action enregistrée pour le moment.\n\n"
            "Le registre se remplit au fil des synthèses de réunions.",
        )
        return
    RegisterWindow(parent, config, items)


class RegisterWindow:
    """Fenêtre de consultation et de mise à jour du registre d'actions."""

    def __init__(self, parent, config, items) -> None:
        self.config = config
        self.items = items  # liste complète d'ActionItem (modifiable en place)
        self._row_items: dict[str, object] = {}
        self._dirty = False

        self.win = tk.Toplevel(parent)
        self.win.title("Registre d'actions")
        self.win.geometry("960x520")
        self.win.minsize(720, 360)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build()
        self._refresh()

    # ------------------------------------------------------------------ UI
    def _build(self) -> None:
        top = ttk.Frame(self.win, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Responsable :").pack(side="left")
        self.resp_var = tk.StringVar(value="Tous")
        responsables = ["Tous"] + sorted({i.responsable for i in self.items})
        resp_combo = ttk.Combobox(
            top, textvariable=self.resp_var, values=responsables, state="readonly", width=22
        )
        resp_combo.pack(side="left", padx=(2, 12))
        resp_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh())

        ttk.Label(top, text="Statut :").pack(side="left")
        self.stat_var = tk.StringVar(value="Tous")
        stat_combo = ttk.Combobox(
            top, textvariable=self.stat_var, values=["Tous"] + STATUSES, state="readonly", width=12
        )
        stat_combo.pack(side="left", padx=2)
        stat_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh())

        self.count_var = tk.StringVar()
        ttk.Label(top, textvariable=self.count_var, foreground="#666").pack(side="right")

        mid = ttk.Frame(self.win)
        mid.pack(fill="both", expand=True, padx=8)
        self.tree = ttk.Treeview(mid, columns=_COLUMNS, show="headings", selectmode="extended")
        for col in _COLUMNS:
            self.tree.heading(col, text=_HEADINGS[col])
            self.tree.column(col, width=_WIDTHS[col], anchor="w")
        vsb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        bottom = ttk.Frame(self.win, padding=8)
        bottom.pack(fill="x")
        ttk.Label(bottom, text="Statut de la sélection :").pack(side="left")
        self.new_status_var = tk.StringVar(value="Fait")
        ttk.Combobox(
            bottom, textvariable=self.new_status_var, values=STATUSES, state="readonly", width=12
        ).pack(side="left", padx=4)
        ttk.Button(bottom, text="Appliquer", command=self._apply_status).pack(side="left", padx=4)
        ttk.Button(bottom, text="💾 Enregistrer", command=self._save).pack(side="right")

    # -------------------------------------------------------------- actions
    def _refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._row_items.clear()
        responsable = None if self.resp_var.get() == "Tous" else self.resp_var.get()
        statut = None if self.stat_var.get() == "Tous" else self.stat_var.get()
        shown = filter_items(self.items, responsable, statut)
        for item in shown:
            iid = self.tree.insert(
                "", "end",
                values=(item.date, item.reunion, item.responsable, item.action,
                        item.echeance, item.statut),
            )
            self._row_items[iid] = item
        self.count_var.set(f"{len(shown)} / {len(self.items)} action(s)")

    def _apply_status(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo(
                "Statut", "Sélectionnez d'abord une ou plusieurs actions dans le tableau."
            )
            return
        new_status = self.new_status_var.get()
        for iid in selection:
            self._row_items[iid].statut = new_status
        self._dirty = True
        self._refresh()

    def _save(self) -> None:
        try:
            paths = write_register(self.config.resolved_output_dir(), self.items)
        except Exception as exc:
            messagebox.showerror("Erreur", f"Enregistrement impossible : {exc}")
            return
        self._dirty = False
        names = ", ".join(p.name for p in paths)
        messagebox.showinfo("Registre d'actions", f"Registre enregistré ({names}).")

    def _on_close(self) -> None:
        if self._dirty and not messagebox.askyesno(
            "Modifications non enregistrées",
            "Des modifications n'ont pas été enregistrées. Fermer quand même ?",
        ):
            return
        self.win.destroy()


__all__ = ["open_register", "RegisterWindow"]
