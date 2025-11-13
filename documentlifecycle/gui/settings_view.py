"""
Settings view – minimal persistence for 'dev borders'.
"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Optional, Any

try:
    from core.settings.logic.settings_manager import SettingsManager  # type: ignore
except Exception:
    class SettingsManager:
        def get(self, *_a, **_k): return None
        def set(self, *_a, **_k): return None


class DocumentLifecycleSettingsView(ttk.Frame):
    _FEATURE_ID = "document_lifecycle"

    def __init__(
        self,
        parent: tk.Misc,
        *,
        settings_manager: Optional[SettingsManager] = None,
        sm: Optional[SettingsManager] = None,
        **_ignore: Any
    ) -> None:
        super().__init__(parent)
        self._sm: SettingsManager = (settings_manager or sm) or SettingsManager()  # type: ignore

        ttk.Label(self, text="Document Lifecycle – Settings", font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 8)
        )

        self._borders = tk.BooleanVar(value=bool(self._sm.get(self._FEATURE_ID, "ui_dev_borders", False)))
        ttk.Checkbutton(self, text="Show development borders", variable=self._borders).grid(
            row=1, column=0, sticky="w", padx=12, pady=4
        )

        btns = ttk.Frame(self); btns.grid(row=2, column=0, sticky="e", padx=12, pady=(4, 12))
        ttk.Button(btns, text="Save", command=self._save).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="Reset", command=self._reset).pack(side="left")

    def _save(self) -> None:
        self._sm.set(self._FEATURE_ID, "ui_dev_borders", bool(self._borders.get()))

    def _reset(self) -> None:
        self._borders.set(False)
