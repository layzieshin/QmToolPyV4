"""
DetailsTab – key/value metadata view for the selected document.

SRP:
- Pure UI for showing metadata fields.
- No business logic, no I/O.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional, Any


class DetailsTab(ttk.Frame):
    """
    Displays document metadata in a simple key/value grid.
    Includes a small placeholder entry (as requested) for visual clarity.
    """

    _FIELDS = ("id", "title", "status", "updated", "author", "version", "path")

    def __init__(self, parent: tk.Widget, **_ignore: Any):
        super().__init__(parent)

        self.columnconfigure(1, weight=1)

        row = 0
        self._labels: dict[str, ttk.Label] = {}

        # Placeholder field first (requested small text field)
        hint = ttk.Entry(self, width=18)
        hint.insert(0, "details placeholder")
        hint.grid(row=row, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 4))
        row += 1

        # Key/Value fields
        for key in self._FIELDS:
            ttk.Label(self, text=f"{key.capitalize()}:").grid(
                row=row, column=0, sticky="w", padx=8, pady=(6, 2)
            )
            val = ttk.Label(self, text="-", anchor="w")
            val.grid(row=row, column=1, sticky="ew", padx=8, pady=(6, 2))
            self._labels[key] = val
            row += 1

        ttk.Separator(self).grid(row=row, column=0, columnspan=2, sticky="ew", padx=8, pady=8)
        row += 1

        # (Room for extensibility if needed)
        # ttk.Label(self, text="...").grid(row=row, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 8))

    # Optional controller wiring (not strictly needed here)
    def attachcontroller(self, _controller) -> None:
        pass

    def render_details(self, doc: Optional[dict]) -> None:
        if not doc:
            for k in self._labels:
                self._labels[k].configure(text="-")
            return
        for k in self._labels:
            self._labels[k].configure(text=str(doc.get(k, "-")))
