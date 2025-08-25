"""
ClockWidget (Tkinter)
---------------------
A clean, responsive clock view that adapts to settings and updates itself.

UX notes:
- Uses a large time label and a secondary date label.
- Respects 24h/12h, seconds, blinking colon, timezone, and custom date format.
- Instantly reflects changes when the settings are saved.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

from ..logic.clock_service import ClockService
from ..logic.clockwork_settings_repository import ClockworkSettingsRepository
from ..models.clockwork_settings import ClockworkSettings


class ClockWidget(ttk.Frame):
    """
    Main clock view. Mount this into any container (e.g., a tab or a panel).

    The widget refreshes itself using Tk's `after` method and supports a live
    settings reload via `reload_settings()`.
    """

    def __init__(self, parent: tk.Misc, app_context: Optional[object] = None) -> None:
        """
        Args:
            parent (tk.Misc): Tk parent container.
            app_context (object, optional): Not required, accepted for integration.
        """
        super().__init__(parent)
        self._app_context = app_context

        # Services & state
        self._repo = ClockworkSettingsRepository()
        self._svc = ClockService()
        self._settings: ClockworkSettings = self._repo.load()
        self._blink_state = True
        self._after_id: Optional[str] = None

        # UI
        self._build_ui()
        self._schedule_tick()

    # --- Public API ---------------------------------------------------------

    def reload_settings(self) -> None:
        """
        Reloads settings from disk and updates the view immediately.
        """
        self._settings = self._repo.load()
        self._update_labels()  # instant reflect
        self._reschedule()

    # --- UI -----------------------------------------------------------------

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)

        self.time_var = tk.StringVar(value="--:--")
        self.date_var = tk.StringVar(value="")

        self.time_label = ttk.Label(self, textvariable=self.time_var, anchor="center")
        self.time_label.configure(font=("Segoe UI", 40, "bold"))
        self.time_label.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 0))

        self.date_label = ttk.Label(self, textvariable=self.date_var, anchor="center")
        self.date_label.configure(font=("Segoe UI", 14))
        self.date_label.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))

        # Tooltip / hint (optional): double-click to refresh settings
        self.bind("<Double-Button-1>", lambda _e: self.reload_settings())
        self.time_label.bind("<Double-Button-1>", lambda _e: self.reload_settings())
        self.date_label.bind("<Double-Button-1>", lambda _e: self.reload_settings())

    # --- Tick loop ----------------------------------------------------------

    def _schedule_tick(self) -> None:
        self._after_id = self.after(self._settings.update_interval_ms, self._on_tick)

    def _reschedule(self) -> None:
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
        self._schedule_tick()

    def _on_tick(self) -> None:
        self._blink_state = not self._blink_state
        self._update_labels()
        self._schedule_tick()

    def _update_labels(self) -> None:
        time_text, date_text = self._svc.format(self._settings, blink_state=self._blink_state)
        self.time_var.set(time_text)
        self.date_var.set(date_text)
