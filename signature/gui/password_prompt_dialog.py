from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from core.common.app_context import T

class PasswordPromptDialog(tk.Toplevel):
    """
    Simple modal dialog asking for a password; returns .password or None.
    Usage:
        dlg = PasswordPromptDialog(parent)
        parent.wait_window(dlg)
        pwd = dlg.password
    """
    def __init__(self, parent: tk.Misc, title: str | None = None) -> None:
        super().__init__(parent)
        self.title(title or (T("core_signature.password.title") or "Password"))
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.password: str | None = None

        ttk.Label(self, text=T("core_signature.password.enter") or "Please enter password:")\
            .grid(row=0, column=0, padx=10, pady=(10, 4), sticky="w")
        self._entry = ttk.Entry(self, show="*"); self._entry.grid(row=1, column=0, padx=10, pady=4, sticky="ew")
        self._entry.focus_set()

        btns = ttk.Frame(self); btns.grid(row=2, column=0, padx=10, pady=(6, 10), sticky="e")
        ttk.Button(btns, text=T("common.cancel") or "Cancel", command=self._on_cancel).pack(side="right", padx=(6, 0))
        ttk.Button(btns, text=T("common.save") or "OK", command=self._on_ok).pack(side="right")

        self.columnconfigure(0, weight=1)
        self.bind("<Return>", lambda e: self._on_ok())
        self.bind("<Escape>", lambda e: self._on_cancel())

    def _on_ok(self):
        self.password = self._entry.get()
        self.destroy()

    def _on_cancel(self):
        self.password = None
        self.destroy()
