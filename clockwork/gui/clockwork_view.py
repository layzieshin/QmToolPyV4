"""
Clockwork – zeigt aktuelle Zeit in gewählter Zeitzone.
(keine Schema-Datei mehr → eigens gestalteter Settings-Tab wird angezeigt)
"""

from __future__ import annotations
import datetime as _dt
import tkinter as tk
from tkinter import ttk
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core.common.app_context import AppContext

MODULE_META = {
    "id": "clockwork",
    "label": "Clockwork",
    "module_path": "clockwork.gui.clockwork_view",
    "class": "ClockworkView",
    "version": "1.0.3",
    "has_settings_view": True,
}

TIMEZONES = {
    "America/Los_Angeles": "Los Angeles",
    "America/New_York": "New York",
    "Europe/Berlin": "Berlin",
    "Australia/Sydney": "Sydney",
}


class ClockworkView(ttk.Frame):
    """Simple digital clock."""

    def __init__(self, parent: tk.Widget, **_):
        super().__init__(parent)
        self._lbl = ttk.Label(self, font=("Consolas", 42), padding=20)
        self._lbl.pack()

        self.sm = AppContext.settings_manager
        self._tz = self._get_tz()
        self._tick()

    # ------------------------------------------------------------------ #
    def _get_tz(self):
        tz_name = self.sm.get(
            "clockwork", "timezone",
            fallback="Europe/Berlin", user_specific=True
        )
        try:
            return ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            return ZoneInfo("Europe/Berlin")

    def _tick(self):
        now = _dt.datetime.now(self._tz).strftime("%H:%M:%S")
        self._lbl.configure(text=now)
        self.after(1000, self._tick)
