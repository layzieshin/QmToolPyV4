"""
CommentsDialog – shows extracted DOCX comments from DB for a document (all versions).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import List, Dict


class CommentsDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, *, comments: List[Dict]) -> None:
        super().__init__(parent)
        self.title("Kommentare")
        self.resizable(True, True)

        frm = ttk.Frame(self, padding=10); frm.grid(sticky="nsew")
        self.columnconfigure(0, weight=1); self.rowconfigure(0, weight=1)

        cols = ("version","author","date","text")
        tree = ttk.Treeview(frm, columns=cols, show="headings", height=16)
        for c, w in [("version",80),("author",160),("date",140),("text",480)]:
            tree.heading(c, text=c.upper()); tree.column(c, width=w, anchor="w", stretch=True if c=="text" else False)
        tree.grid(row=0, column=0, sticky="nsew")
        for c in comments:
            tree.insert("", "end", values=(c.get("version_label"), c.get("author",""), c.get("date",""), c.get("text","")))
        ttk.Button(frm, text="Schließen", command=self.destroy).grid(row=1, column=0, sticky="e", pady=(8,0))
