"""
core/settings/gui/settings_view.py
==================================

Notebook for all settings tabs.

Design:
- Only settings tabs provided by each module's `settings_class`.
- Each specialized settings tab is self-contained (own Save/Validate).
- Admin tabs: Config + Module Mgmt.
"""

from __future__ import annotations

import importlib
import tkinter as tk
from tkinter import ttk

from core.common.app_context import AppContext, T
from core.common.module_registry import load_registry
from core.config.gui.config_settings_view import ConfigSettingsTab
from core.settings.gui.modules_config_tab import ModulesConfigTab
from core.settings.logic.settings_manager import SettingsManager
from core.models.user import UserRole


class SettingsView(ttk.Frame):
    """Root view hosting all settings tabs."""

    def __init__(self, parent: tk.Widget):
        super().__init__(parent)

        self.sm: SettingsManager = AppContext.settings_manager
        self._is_admin: bool = (
            AppContext.current_user and AppContext.current_user.role == UserRole.ADMIN
        )

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=6)
        self._nb = nb

        # Module settings tabs (settings_class only)
        role = AppContext.current_user.role if AppContext.current_user else None
        for desc in load_registry(role=None).values():
            if not desc.settings_class:
                continue
            if not desc.allowed_in_settings(role):
                continue
            try:
                pkg, cls_name = desc.settings_class.rsplit(".", 1)
                smod = importlib.import_module(pkg)
                cls = getattr(smod, cls_name)
                # Pass shared SettingsManager to each tab
                tab = cls(self._nb, sm=self.sm)
                self._nb.add(tab, text=f"{desc.label} ⚙")
            except Exception as exc:
                print(f"[WARN] Failed to load settings_class for {desc.id}: {exc}")

        # Admin tabs
        if self._is_admin:
            self._nb.add(ConfigSettingsTab(self._nb), text=T("config"))
            self._nb.add(ModulesConfigTab(self._nb), text="Module Mgmt")
