"""
Clockwork – main view (auto-loaded via meta.json).
Shows a timezone-aware clock with optional date line.

Conventions:
- Constructor only requests injectables (resolved by MainWindow via AppContext.services).
- Settings are read via SettingsManager and cached locally.
- Double-click anywhere on the view triggers a settings reload.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass
from typing import Optional

from core.common.app_context import AppContext  # for current_user + T()
from core.settings.logic.settings_manager import SettingsManager  # injected instance
from clockwork.logic.clock_service import ClockService


@dataclass
class _ClockCfg:
    """Local, immutable snapshot of user settings."""
    timezone: str = "Europe/Berlin"
    use_24h: bool = True
    show_seconds: bool = True
    show_date: bool = True
    date_format: str = "%Y-%m-%d"
    blink_colon: bool = False
    update_interval_ms: int = 250


class ClockworkView(ttk.Frame):
    """
    Auto-loaded feature view.

    DI (auto-injected by MainWindow via signature introspection):
        settings_manager: SettingsManager
    """

    def __init__(self, parent: tk.Misc, *, settings_manager: SettingsManager) -> None:
        super().__init__(parent)
        self._sm = settings_manager
        self._svc = ClockService()

        self._cfg = self._load_cfg()
        self._blink_state = True
        self._after_id: Optional[str] = None

        # --- UI --------------------------------------------------------
        self.columnconfigure(0, weight=1)
        self.time_var = tk.StringVar(value="--:--")
        self.date_var = tk.StringVar(value="")

        self.time_lbl = ttk.Label(self, textvariable=self.time_var, anchor="center")
        self.time_lbl.configure(font=("Segoe UI", 40, "bold"))
        self.time_lbl.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 0))

        self.date_lbl = ttk.Label(self, textvariable=self.date_var, anchor="center")
        self.date_lbl.configure(font=("Segoe UI", 14))
        self.date_lbl.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))

        # UX: double-click to reload settings immediately
        for w in (self, self.time_lbl, self.date_lbl):
            w.bind("<Double-Button-1>", lambda _e: self.reload_settings())

        # Start ticking
        self._schedule_tick(initial=True)

    # ------------------------------------------------------------------ #
    # Settings handling                                                  #
    # ------------------------------------------------------------------ #
    def _load_cfg(self) -> _ClockCfg:
        """Reads user-specific settings from SettingsManager, with safe fallbacks."""
        user = getattr(AppContext, "current_user", None)
        uid = getattr(user, "id", None)

        def get(key: str, default):
            if uid:
                return self._sm.get("clockwork", key, default, user_specific=True, user_id=uid)
            return self._sm.get("clockwork", key, default, user_specific=False)

        return _ClockCfg(
            timezone=str(get("timezone", "Europe/Berlin")),
            use_24h=bool(get("use_24h", True)),
            show_seconds=bool(get("show_seconds", True)),
            show_date=bool(get("show_date", True)),
            date_format=str(get("date_format", "%Y-%m-%d")),
            blink_colon=bool(get("blink_colon", False)),
            update_interval_ms=int(get("update_interval_ms", 250)),
        )

    def reload_settings(self) -> None:
        """Public hook to reload settings on demand."""
        self._cfg = self._load_cfg()
        # Re-arm timer with new update interval
        self._reschedule()
        self._update_labels()

    # ------------------------------------------------------------------ #
    # Tick loop / rendering                                              #
    # ------------------------------------------------------------------ #
    def _schedule_tick(self, *, initial: bool = False) -> None:
        if initial:
            # First immediate paint avoids visible lag
            self._update_labels()
        self._after_id = self.after(self._cfg.update_interval_ms, self._on_tick)

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
        time_text, date_text = self._svc.format(
            timezone=self._cfg.timezone,
            use_24h=self._cfg.use_24h,
            show_seconds=self._cfg.show_seconds,
            show_date=self._cfg.show_date,
            date_format=self._cfg.date_format,
            blink_colon=self._cfg.blink_colon,
            blink_state=self._blink_state,
        )
        self.time_var.set(time_text)
        self.date_var.set(date_text)
