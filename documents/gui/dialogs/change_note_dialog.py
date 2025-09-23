"""
Dialog to collect a mandatory change note for status transitions / check-in.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from documents.gui.i18n import tr


class ChangeNoteDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, title: str) -> None:
        super().__init__(parent)
        self.title(title)
        self.resizable(True, True)
        self.result: str | None = None

        frm = ttk.Frame(self, padding=12)
        frm.grid(sticky="nsew")
        self.columnconfigure(0, weight=1); self.rowconfigure(0, weight=1)
        ttk.Label(frm, text=tr("documents.changenote.prompt", "Please describe the reason/change:")).grid(
            row=0, column=0, sticky="w"
        )
        self.txt = tk.Text(frm, width=60, height=8)
        self.txt.grid(row=1, column=0, sticky="nsew", pady=8)

        btns = ttk.Frame(frm); btns.grid(row=2, column=0, sticky="e")
        ttk.Button(btns, text=tr("common.cancel", "Cancel"), command=self.destroy).grid(row=0, column=0, padx=(0,6))
        ttk.Button(btns, text=tr("common.ok", "OK"), command=self._ok).grid(row=0, column=1)

        self.transient(parent); self.grab_set(); self.txt.focus_set()
        self.wait_visibility(); self.wm_attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _ok(self) -> None:
        self.result = self.txt.get("1.0", "end").strip()
        self.destroy()
