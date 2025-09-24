"""
TasksDialog – shows pending workflow tasks for the current user.
Each row exposes the next actionable step which calls back into main view.

Internationalization:
- Title, column headings and close label via tr("documents.tasks.*").
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Dict

from documents.gui.i18n import tr


class TasksDialog(tk.Toplevel):
    """Modal dialog listing user's workflow tasks with double-click action."""

    COLS = ("doc_id", "title", "status", "version", "next_action", "go")

    def __init__(self, parent: tk.Misc, *, tasks: List[Dict], on_action: Callable[[str, str], None]) -> None:
        super().__init__(parent)
        self._on_action = on_action

        # Window configuration
        self.title(tr("documents.tasks.title", "My workflows"))
        self.resizable(True, True)

        # Layout
        frm = ttk.Frame(self, padding=10)
        frm.grid(sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Column labels (translated)
        headings = {
            "doc_id": tr("documents.tasks.col.doc_id", "Document ID"),
            "title": tr("documents.tasks.col.title", "Title"),
            "status": tr("documents.tasks.col.status", "Status"),
            "version": tr("documents.tasks.col.version", "Version"),
            "next_action": tr("documents.tasks.col.next_action", "Next action"),
            "go": tr("documents.tasks.col.go", "Go"),
        }

        self.tree = ttk.Treeview(frm, columns=self.COLS, show="headings", height=16, selectmode="browse")
        for c, w in [("doc_id", 160), ("title", 220), ("status", 100), ("version", 60), ("next_action", 140), ("go", 60)]:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=w, stretch=True if c in ("title",) else False, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")

        # Rows
        for t in tasks:
            self.tree.insert(
                "",
                "end",
                iid=t["doc_id"],
                values=(
                    t.get("doc_id", ""),
                    t.get("title", ""),
                    t.get("status", ""),
                    t.get("version", ""),
                    t.get("next_action", ""),
                    "▶",
                ),
            )

        self.tree.bind("<Double-1>", self._dbl)

        ttk.Button(frm, text=tr("documents.tasks.close", "Close"), command=self.destroy).grid(
            row=1, column=0, sticky="e", pady=(8, 0)
        )

        # Modal behavior
        self.transient(parent)
        self.grab_set()
        self.wait_visibility()
        self.wm_attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _dbl(self, _evt=None) -> None:
        """Double-click triggers the task's next_action callback and closes the dialog."""
        sel = self.tree.selection()
        if not sel:
            return
        doc_id = sel[0]
        action = self.tree.set(doc_id, "next_action")
        if action:
            self._on_action(doc_id, action)
            self.destroy()
