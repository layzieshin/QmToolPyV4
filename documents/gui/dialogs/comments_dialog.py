"""
CommentsDialog – shows extracted DOCX comments from DB for a document (all versions).

Internationalization:
- Title, column headings and close button are translated via tr("documents.comments.*").
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import List, Dict

from documents.gui.i18n import tr


class CommentsDialog(tk.Toplevel):
    """Modal dialog showing all comments for a document (all versions)."""

    COLS = ("version", "author", "date", "text")

    def __init__(self, parent: tk.Misc, *, comments: List[Dict]) -> None:
        super().__init__(parent)

        # Window configuration
        self.title(tr("documents.comments.title", "Comments"))
        self.resizable(True, True)

        # Layout
        frm = ttk.Frame(self, padding=10)
        frm.grid(sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Column labels (translated)
        headings = {
            "version": tr("documents.comments.col.version", "Version"),
            "author": tr("documents.comments.col.author", "Author"),
            "date": tr("documents.comments.col.date", "Date"),
            "text": tr("documents.comments.col.text", "Text"),
        }

        tree = ttk.Treeview(frm, columns=self.COLS, show="headings", height=16, selectmode="browse")
        for c, w in [("version", 80), ("author", 160), ("date", 140), ("text", 480)]:
            tree.heading(c, text=headings[c])
            tree.column(c, width=w, anchor="w", stretch=True if c == "text" else False)
        tree.grid(row=0, column=0, sticky="nsew")

        # Data
        for c in comments:
            tree.insert(
                "",
                "end",
                values=(
                    c.get("version_label", ""),
                    c.get("author", ""),
                    c.get("date", ""),
                    c.get("text", ""),
                ),
            )

        ttk.Button(frm, text=tr("documents.comments.close", "Close"), command=self.destroy).grid(
            row=1, column=0, sticky="e", pady=(8, 0)
        )

        # Modal behavior
        self.transient(parent)
        self.grab_set()
        self.wait_visibility()
        self.wm_attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
