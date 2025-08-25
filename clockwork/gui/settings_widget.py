"""
ClockworkSettingsWidget (Tkinter)
---------------------------------
Settings UI for the Clockwork feature with immediate validation and
atomic persistence.

UX:
- Clear grouping, helpful descriptions, live preview.
- Save writes to config.ini and, if a running ClockWidget exists, it can
  refresh its view via the provided callback (optional).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Callable

try:
    from zoneinfo import ZoneInfo, available_timezones  # py311+ for listing
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

from ..logic.clockwork_settings_repository import ClockworkSettingsRepository
from ..logic.clock_service import ClockService
from ..models.clockwork_settings import ClockworkSettings


class ClockworkSettingsWidget(ttk.Frame):
    """
    Settings editor for the clockwork module.

    Optional `on_saved` callback allows the host to refresh a live clock view.
    """

    def __init__(
        self,
        parent: tk.Misc,
        app_context: Optional[object] = None,
        on_saved: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent)
        self._app_context = app_context
        self._on_saved = on_saved

        self._repo = ClockworkSettingsRepository()
        self._svc = ClockService()
        self._settings: ClockworkSettings = self._repo.load()

        self._build_ui()
        self._populate_from_model()
        self._update_preview()

    # --- UI -----------------------------------------------------------------

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)

        # Timezone
        ttk.Label(self, text=self._t("clockwork.settings.timezone", "Timezone")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(12, 6)
        )

        # Prefer a combobox with available timezones if supported
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

        # 24h / seconds / blink
        self.use_24h_var = tk.BooleanVar(value=True)
        self.show_seconds_var = tk.BooleanVar(value=True)
        self.blink_colon_var = tk.BooleanVar(value=False)

        self.use_24h_chk = ttk.Checkbutton(
            self, text=self._t("clockwork.settings.use_24h", "Use 24-hour clock"), variable=self.use_24h_var,
            command=self._update_preview
        )
        self.use_24h_chk.grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=4)

        self.show_seconds_chk = ttk.Checkbutton(
            self, text=self._t("clockwork.settings.show_seconds", "Show seconds"), variable=self.show_seconds_var,
            command=self._update_preview
        )
        self.show_seconds_chk.grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=4)

        self.blink_colon_chk = ttk.Checkbutton(
            self, text=self._t("clockwork.settings.blink_colon", "Blink colon"), variable=self.blink_colon_var,
            command=self._update_preview
        )
        self.blink_colon_chk.grid(row=3, column=0, columnspan=2, sticky="w", padx=10, pady=4)

        # Date line
        self.show_date_var = tk.BooleanVar(value=True)
        self.show_date_chk = ttk.Checkbutton(
            self, text=self._t("clockwork.settings.show_date", "Show date line"), variable=self.show_date_var,
            command=self._update_preview
        )
        self.show_date_chk.grid(row=4, column=0, columnspan=2, sticky="w", padx=10, pady=4)

        ttk.Label(self, text=self._t("clockwork.settings.date_format", "Date format")).grid(
            row=5, column=0, sticky="w", padx=10, pady=4
        )
        self.date_format_ctrl = ttk.Entry(self)
        self.date_format_ctrl.grid(row=5, column=1, sticky="ew", padx=10, pady=4)

        # Update interval
        ttk.Label(self, text=self._t("clockwork.settings.update_ms", "Update interval (ms)")).grid(
            row=6, column=0, sticky="w", padx=10, pady=4
        )
        self.update_ms_ctrl = ttk.Spinbox(self, from_=50, to=5000, increment=50)
        self.update_ms_ctrl.grid(row=6, column=1, sticky="w", padx=10, pady=4)

        # Preview
        ttk.Separator(self).grid(row=7, column=0, columnspan=2, sticky="ew", padx=10, pady=8)
        ttk.Label(self, text=self._t("clockwork.settings.preview", "Preview")).grid(
            row=8, column=0, sticky="w", padx=10, pady=(0, 4)
        )

        self.preview_time_var = tk.StringVar(value="")
        self.preview_date_var = tk.StringVar(value="")
        self.preview_time_lbl = ttk.Label(self, textvariable=self.preview_time_var, font=("Segoe UI", 18, "bold"))
        self.preview_date_lbl = ttk.Label(self, textvariable=self.preview_date_var, font=("Segoe UI", 11))
        self.preview_time_lbl.grid(row=9, column=0, columnspan=2, sticky="w", padx=10)
        self.preview_date_lbl.grid(row=10, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 8))

        # Buttons
        ttk.Separator(self).grid(row=11, column=0, columnspan=2, sticky="ew", padx=10, pady=8)
        btns = ttk.Frame(self)
        btns.grid(row=12, column=0, columnspan=2, sticky="e", padx=10, pady=(0, 12))

        self.save_btn = ttk.Button(btns, text=self._t("common.save", "Save"), command=self._on_save)
        self.reset_btn = ttk.Button(btns, text=self._t("common.reset", "Reset to defaults"), command=self._on_reset)
        self.save_btn.grid(row=0, column=0, padx=(0, 6))
        self.reset_btn.grid(row=0, column=1)

    # --- Data binding -------------------------------------------------------

    def _populate_from_model(self) -> None:
        s = self._settings
        self._set_text(self.timezone_ctrl, s.timezone)
        self.use_24h_var.set(s.use_24h)
        self.show_seconds_var.set(s.show_seconds)
        self.blink_colon_var.set(s.blink_colon)
        self.show_date_var.set(s.show_date)
        self._set_text(self.date_format_ctrl, s.date_format)
        self.update_ms_ctrl.delete(0, "end")
        self.update_ms_ctrl.insert(0, str(s.update_interval_ms))

    def _collect_to_model(self) -> Optional[ClockworkSettings]:
        tz = self._get_text(self.timezone_ctrl).strip() or "Europe/Berlin"
        if ZoneInfo:
            try:
                _ = ZoneInfo(tz)
            except Exception:
                messagebox.showerror(
                    title=self._t("clockwork.error.invalid_tz_title", "Invalid timezone"),
                    message=self._t("clockwork.error.invalid_tz_msg",
                                    "The timezone you entered is not valid. Please provide a valid IANA timezone, e.g., Europe/Berlin."),
                )
                return None

        try:
            update_ms = int(self.update_ms_ctrl.get())
            if update_ms < 50:
                update_ms = 50
        except Exception:
            update_ms = 250

        return ClockworkSettings(
            timezone=tz,
            show_seconds=bool(self.show_seconds_var.get()),
            use_24h=bool(self.use_24h_var.get()),
            show_date=bool(self.show_date_var.get()),
            date_format=self._get_text(self.date_format_ctrl).strip() or "%Y-%m-%d",
            blink_colon=bool(self.blink_colon_var.get()),
            update_interval_ms=update_ms,
        )

    # --- Actions ------------------------------------------------------------

    def _on_save(self) -> None:
        model = self._collect_to_model()
        if model is None:
            return

        # Persist atomically; reload internal state; refresh preview
        self._repo.save(model)
        self._settings = self._repo.load()
        self._update_preview()

        # Notify host to refresh a running clock view if provided
        if callable(self._on_saved):
            try:
                self._on_saved()
            except Exception:
                pass

        messagebox.showinfo(
            title=self._t("clockwork.info.saved", "Settings saved"),
            message=self._t("clockwork.info.saved_msg", "Your Clockwork settings have been saved."),
        )

    def _on_reset(self) -> None:
        self._settings = ClockworkSettings()
        self._populate_from_model()
        self._update_preview()

    # --- Preview ------------------------------------------------------------

    def _update_preview(self) -> None:
        # Get a "virtual" formatting without changing persisted model
        tmp = self._collect_to_model()
        if tmp is None:
            tmp = self._settings
        t, d = self._svc.format(tmp, blink_state=True)
        self.preview_time_var.set(t)
        self.preview_date_var.set(d)

    # --- Helpers ------------------------------------------------------------

    @staticmethod
    def _get_text(ctrl: tk.Widget) -> str:
        if isinstance(ctrl, ttk.Entry) or isinstance(ctrl, tk.Entry):
            return ctrl.get()
        if isinstance(ctrl, ttk.Combobox):
            return ctrl.get()
        return ""

    @staticmethod
    def _set_text(ctrl: tk.Widget, value: str) -> None:
        if isinstance(ctrl, ttk.Entry) or isinstance(ctrl, tk.Entry):
            ctrl.delete(0, "end")
            ctrl.insert(0, value)
        elif isinstance(ctrl, ttk.Combobox):
            ctrl.set(value)

    @staticmethod
    def _t(key: str, default: str) -> str:
        try:
            from core.locale import LocaleManager  # type: ignore
            try:
                lm = LocaleManager.instance()
            except Exception:
                try:
                    lm = LocaleManager.get_instance()
                except Exception:
                    lm = None
            if lm is not None:
                return lm.t(key) or default
        except Exception:
            pass
        return default
