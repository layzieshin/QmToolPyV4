"""
ClockworkSettingsTab – specialized settings UI for the Clockwork feature.

Loaded by the central settings notebook via desc.settings_class (see meta.json).
Persists settings per user using SettingsManager, with validation and live preview.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

try:
    # Python 3.11+: available_timezones; we keep a graceful fallback.
    from zoneinfo import ZoneInfo, available_timezones
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

from core.common.app_context import AppContext, T  # user + translations
from core.settings.logic.settings_manager import SettingsManager
from clockwork.logic.clock_service import ClockService


class ClockworkSettingsTab(ttk.Frame):
    """Settings editor for Clockwork (instantiated as `ClockworkSettingsTab(parent, sm=<SettingsManager>)`)."""

    SETTINGS_TAB = True  # marker (not strictly required, kept for clarity)

    def __init__(self, parent: tk.Misc, *, sm: SettingsManager) -> None:
        super().__init__(parent)
        self._sm: SettingsManager = sm
        self._svc = ClockService()

        self.columnconfigure(1, weight=1)

        # --- Timezone ---------------------------------------------------
        ttk.Label(self, text=T("clockwork.settings.timezone") or "Timezone").grid(
            row=0, column=0, sticky="w", padx=10, pady=(12, 6)
        )

        tz_values = None
        if callable(globals().get("available_timezones", None)):
            try:
                tz_values = sorted(available_timezones())  # type: ignore
            except Exception:
                tz_values = None

        if tz_values:
            self.timezone_ctrl = ttk.Combobox(self, values=tz_values, state="normal")
        else:
            self.timezone_ctrl = ttk.Entry(self)

        self.timezone_ctrl.grid(row=0, column=1, sticky="ew", padx=10, pady=(12, 6))

        # --- Booleans ---------------------------------------------------
        self.use_24h_var = tk.BooleanVar(value=True)
        self.show_seconds_var = tk.BooleanVar(value=True)
        self.show_date_var = tk.BooleanVar(value=True)
        self.blink_colon_var = tk.BooleanVar(value=False)

        self.use_24h_chk = ttk.Checkbutton(self,
            text=T("clockwork.settings.use_24h") or "Use 24-hour clock",
            variable=self.use_24h_var, command=self._update_preview)
        self.show_seconds_chk = ttk.Checkbutton(self,
            text=T("clockwork.settings.show_seconds") or "Show seconds",
            variable=self.show_seconds_var, command=self._update_preview)
        self.show_date_chk = ttk.Checkbutton(self,
            text=T("clockwork.settings.show_date") or "Show date line",
            variable=self.show_date_var, command=self._update_preview)
        self.blink_colon_chk = ttk.Checkbutton(self,
            text=T("clockwork.settings.blink_colon") or "Blink colon",
            variable=self.blink_colon_var, command=self._update_preview)

        self.use_24h_chk.grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=4)
        self.show_seconds_chk.grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=4)
        self.blink_colon_chk.grid(row=3, column=0, columnspan=2, sticky="w", padx=10, pady=4)
        self.show_date_chk.grid(row=4, column=0, columnspan=2, sticky="w", padx=10, pady=4)

        # --- Date format ------------------------------------------------
        ttk.Label(self, text=T("clockwork.settings.date_format") or "Date format").grid(
            row=5, column=0, sticky="w", padx=10, pady=4
        )
        self.date_format_ctrl = ttk.Entry(self)
        self.date_format_ctrl.grid(row=5, column=1, sticky="ew", padx=10, pady=4)

        # --- Update interval -------------------------------------------
        ttk.Label(self, text=T("clockwork.settings.update_ms") or "Update interval (ms)").grid(
            row=6, column=0, sticky="w", padx=10, pady=4
        )
        self.update_ms_ctrl = ttk.Spinbox(self, from_=50, to=5000, increment=50)
        self.update_ms_ctrl.grid(row=6, column=1, sticky="w", padx=10, pady=4)

        # --- Preview ----------------------------------------------------
        ttk.Separator(self).grid(row=7, column=0, columnspan=2, sticky="ew", padx=10, pady=8)
        ttk.Label(self, text=T("clockwork.settings.preview") or "Preview").grid(
            row=8, column=0, sticky="w", padx=10, pady=(0, 4)
        )
        self.preview_time_var = tk.StringVar(value="")
        self.preview_date_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.preview_time_var, font=("Segoe UI", 18, "bold")).grid(
            row=9, column=0, columnspan=2, sticky="w", padx=10
        )
        ttk.Label(self, textvariable=self.preview_date_var, font=("Segoe UI", 11)).grid(
            row=10, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 8)
        )

        # --- Buttons ----------------------------------------------------
        ttk.Separator(self).grid(row=11, column=0, columnspan=2, sticky="ew", padx=10, pady=8)
        btns = ttk.Frame(self)
        btns.grid(row=12, column=0, columnspan=2, sticky="e", padx=10, pady=(0, 12))
        ttk.Button(btns, text=T("common.save") or "Save", command=self._on_save).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(btns, text=T("common.reset") or "Reset to defaults", command=self._on_reset).grid(row=0, column=1)

        # Populate & initial preview
        self._load_from_store()
        self._update_preview()

    # ------------------------------------------------------------------ #
    # Data binding                                                       #
    # ------------------------------------------------------------------ #
    def _load_from_store(self) -> None:
        """Pulls current settings from store (per user if available)."""
        user = getattr(AppContext, "current_user", None)
        uid = getattr(user, "id", None)

        def get(key: str, default):
            if uid:
                return self._sm.get("clockwork", key, default, user_specific=True, user_id=uid)
            return self._sm.get("clockwork", key, default)

        tz = str(get("timezone", "Europe/Berlin"))
        if isinstance(self.timezone_ctrl, ttk.Combobox):
            self.timezone_ctrl.set(tz)
        else:
            self.timezone_ctrl.delete(0, "end")
            self.timezone_ctrl.insert(0, tz)

        self.use_24h_var.set(bool(get("use_24h", True)))
        self.show_seconds_var.set(bool(get("show_seconds", True)))
        self.show_date_var.set(bool(get("show_date", True)))
        self.blink_colon_var.set(bool(get("blink_colon", False)))
        self.date_format_ctrl.delete(0, "end")
        self.date_format_ctrl.insert(0, str(get("date_format", "%Y-%m-%d")))

        self.update_ms_ctrl.delete(0, "end")
        self.update_ms_ctrl.insert(0, str(int(get("update_interval_ms", 250))))

    def _collect(self) -> dict | None:
        """Reads UI state and validates values."""
        tz = self._get_text(self.timezone_ctrl).strip() or "Europe/Berlin"
        if ZoneInfo:
            try:
                _ = ZoneInfo(tz)
            except Exception:
                messagebox.showerror(
                    title=T("clockwork.error.invalid_tz_title") or "Invalid timezone",
                    message=T("clockwork.error.invalid_tz_msg")
                            or "Please provide a valid IANA timezone, e.g., Europe/Berlin.",
                    parent=self,
                )
                return None

        try:
            update_ms = int(self.update_ms_ctrl.get())
            if update_ms < 50:
                update_ms = 50
        except Exception:
            update_ms = 250

        return {
            "timezone": tz,
            "use_24h": bool(self.use_24h_var.get()),
            "show_seconds": bool(self.show_seconds_var.get()),
            "show_date": bool(self.show_date_var.get()),
            "date_format": self._get_text(self.date_format_ctrl).strip() or "%Y-%m-%d",
            "blink_colon": bool(self.blink_colon_var.get()),
            "update_interval_ms": update_ms,
        }

    # ------------------------------------------------------------------ #
    # Actions                                                            #
    # ------------------------------------------------------------------ #
    def _on_save(self) -> None:
        data = self._collect()
        if data is None:
            return

        user = getattr(AppContext, "current_user", None)
        uid = getattr(user, "id", None)

        # Persist atomically via repository layer (SettingsManager handles that)
        for k, v in data.items():
            if uid:
                self._sm.set("clockwork", k, v, user_specific=True, user_id=uid)
            else:
                self._sm.set("clockwork", k, v)

        messagebox.showinfo(
            title=T("clockwork.info.saved") or "Settings saved",
            message=T("clockwork.info.saved_msg") or "Your Clockwork settings have been saved.",
            parent=self,
        )

        # Update preview after save
        self._update_preview()

    def _on_reset(self) -> None:
        """Resets to sane defaults in the editor (does not write immediately)."""
        if isinstance(self.timezone_ctrl, ttk.Combobox):
            self.timezone_ctrl.set("Europe/Berlin")
        else:
            self.timezone_ctrl.delete(0, "end")
            self.timezone_ctrl.insert(0, "Europe/Berlin")
        self.use_24h_var.set(True)
        self.show_seconds_var.set(True)
        self.show_date_var.set(True)
        self.blink_colon_var.set(False)
        self.date_format_ctrl.delete(0, "end")
        self.date_format_ctrl.insert(0, "%Y-%m-%d")
        self.update_ms_ctrl.delete(0, "end")
        self.update_ms_ctrl.insert(0, "250")
        self._update_preview()

    # ------------------------------------------------------------------ #
    # Preview                                                            #
    # ------------------------------------------------------------------ #
    def _update_preview(self) -> None:
        tmp = self._collect()
        if not tmp:
            return
        time_text, date_text = self._svc.format(
            timezone=tmp["timezone"],
            use_24h=tmp["use_24h"],
            show_seconds=tmp["show_seconds"],
            show_date=tmp["show_date"],
            date_format=tmp["date_format"],
            blink_colon=tmp["blink_colon"],
            blink_state=True,
        )
        self.preview_time_var.set(time_text)
        self.preview_date_var.set(date_text)

    # ------------------------------------------------------------------ #
    # Helpers                                                            #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _get_text(ctrl: tk.Widget) -> str:
        if isinstance(ctrl, ttk.Entry) or isinstance(ctrl, tk.Entry):
            return ctrl.get()
        if isinstance(ctrl, ttk.Combobox):
            return ctrl.get()
        return ""
