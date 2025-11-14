"""
Import dialog – collects a file path (later: metadata) and returns it to the controller.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog


class ImportDialog(ttk.Frame):
    """Minimal, embeddable dialog."""

    def __init__(self, parent: tk.Widget, on_confirm, **_ignore):
        super().__init__(parent)
        self._on_confirm = on_confirm

        self._path_var = tk.StringVar()

        row = 0
        ttk.Label(self, text="Select document file:").grid(row=row, column=0, sticky="w", padx=8, pady=8)
        ttk.Entry(self, textvariable=self._path_var, width=44).grid(row=row, column=1, sticky="ew", padx=8, pady=8)
        ttk.Button(self, text="Browse...", command=self._browse).grid(row=row, column=2, sticky="w", padx=8, pady=8)

        row += 1
        actions = ttk.Frame(self); actions.grid(row=row, column=0, columnspan=3, sticky="e", padx=8, pady=8)
        ttk.Button(actions, text="Cancel", command=self._cancel).pack(side="right", padx=4)
        ttk.Button(actions, text="Import", command=self._confirm).pack(side="right", padx=4)

        self.columnconfigure(1, weight=1)

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Select file",
            filetypes=[("Word/PDF", "*.docx *.pdf"), ("All", "*.*")]
        )
        if path:
            self._path_var.set(path)

    def _cancel(self):
        self.winfo_toplevel().destroy()

    def _confirm(self):
        self._on_confirm(self._path_var.get())
        self.winfo_toplevel().destroy()
