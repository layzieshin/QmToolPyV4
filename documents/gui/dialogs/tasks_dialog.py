"""
TasksDialog – shows pending workflow tasks for the current user.
Each row exposes the next actionable step which calls back into main view.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Dict


class TasksDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, *, tasks: List[Dict], on_action: Callable[[str, str], None]) -> None:
        super().__init__(parent)
        self.title("Meine Workflows")
        self.resizable(True, True)
        self._on_action = on_action

        frm = ttk.Frame(self, padding=10); frm.grid(sticky="nsew")
        self.columnconfigure(0, weight=1); self.rowconfigure(0, weight=1)

        cols = ("doc_id","title","status","version","next_action","go")
        self.tree = ttk.Treeview(frm, columns=cols, show="headings", height=16, selectmode="browse")
        for c, w in [("doc_id",160),("title",220),("status",100),("version",60),("next_action",140),("go",60)]:
            self.tree.heading(c, text=c.upper())
            self.tree.column(c, width=w, stretch=True if c in ("title",) else False, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")

        for t in tasks:
            self.tree.insert("", "end", iid=t["doc_id"], values=(
                t["doc_id"], t["title"], t["status"], t["version"], t["next_action"], "▶"
            ))

        self.tree.bind("<Double-1>", self._dbl)
        ttk.Button(frm, text="Schließen", command=self.destroy).grid(row=1, column=0, sticky="e", pady=(8,0))

    def _dbl(self, _evt=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        doc_id = sel[0]
        action = self.tree.set(doc_id, "next_action")
        if action:
            self._on_action(doc_id, action)
            self.destroy()
