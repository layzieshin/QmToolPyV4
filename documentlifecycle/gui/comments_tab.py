"""
CommentsTab – comment list placeholder for the selected document.

SRP:
- Pure UI for comments (list + small input placeholders).
- No persistence here; controller/service will be wired later.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, List, Dict


class CommentsTab(ttk.Frame):
    """
    Shows a simple list of comments and a small placeholder entry.
    """

    def __init__(self, parent: tk.Widget, **_ignore: Any):
        super().__init__(parent)

        # Layout
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Small placeholder as requested
        hint = ttk.Entry(self, width=18)
        hint.insert(0, "comments placeholder")
        hint.grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))

        # Comments list (Treeview) – simple columns
        self._tree = ttk.Treeview(
            self,
            columns=("author", "date", "text"),
            show="headings",
            selectmode="browse",
            height=8,
        )
        self._tree.heading("author", text="Author")
        self._tree.heading("date", text="Date")
        self._tree.heading("text", text="Comment")
        self._tree.column("author", width=120, anchor="w")
        self._tree.column("date", width=110, anchor="center")
        self._tree.column("text", width=400, anchor="w")
        self._tree.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        yscroll = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=yscroll.set)
        yscroll.grid(row=1, column=1, sticky="ns", pady=(0, 8))

        # Bottom row – placeholder inputs & buttons (no logic attached yet)
        bottom = ttk.Frame(self)
        bottom.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))
        bottom.columnconfigure(2, weight=1)

        self._author_var = tk.StringVar(value="")
        self._text_var = tk.StringVar(value="")
        ttk.Label(bottom, text="Author:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Entry(bottom, textvariable=self._author_var, width=18).grid(row=0, column=1, sticky="w", padx=(0, 12))
        ttk.Entry(bottom, textvariable=self._text_var).grid(row=0, column=2, sticky="ew", padx=(0, 12))
        ttk.Button(bottom, text="Add", command=self._on_add_placeholder).grid(row=0, column=3, sticky="e")

    # Optional controller wiring
    def attach_controller(self, controller) -> None:
        self._controller = controller  # not used yet, kept for future wiring

    # Render a list of comments
    def render_comments(self, comments: List[Dict[str, Any]]) -> None:
        self._tree.delete(*self._tree.get_children())
        for c in comments:
            self._tree.insert(
                "", "end",
                values=(c.get("author", "-"), c.get("date", "-"), c.get("text", "-"))
            )

    # Placeholder: local add (no persistence – just visual feedback)
    def _on_add_placeholder(self) -> None:
        author = (self._author_var.get() or "").strip() or "-"
        text = (self._text_var.get() or "").strip()
        if not text:
            return
        self._tree.insert("", "end", values=(author, "—", text))
        self._text_var.set("")
