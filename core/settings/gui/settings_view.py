"""
core/settings/gui/settings_view.py
==================================

Root GUI view grouping all settings tabs.

• Dynamically assembles notebook tabs based on SETTINGS_SCHEMA discovered in
  registered modules.
• Adds an extra *Config* tab for ADMIN users.
"""

from __future__ import annotations

import importlib
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List, Tuple

from core.common.app_context import AppContext
from core.settings.logic.settings_manager import SettingsManager
from core.common.module_registry import load_registry
from core.i18n.translation_manager import T
from core.models.user import UserRole
from core.config.gui.config_settings_view import ConfigSettingsTab


class SettingsView(ttk.Frame):
    """Root view that groups together *all* settings tabs.

    The notebook populates itself dynamically based on
    ``SETTINGS_SCHEMA`` definitions found in registered modules.  If the current
    user holds the role :pydata:`~core.models.user.UserRole.ADMIN`, an additional
    *Config* tab (managed by :class:`ConfigSettingsTab`) will be appended.
    """

    def __init__(self, parent):
        super().__init__(parent)

        self.sm: SettingsManager = AppContext.settings_manager
        self._is_admin: bool = (
            AppContext.current_user is not None
            and AppContext.current_user.role == UserRole.ADMIN
        )
        self._fields: List[Tuple[Dict, tk.Variable]] = []

        # Notebook with module-specific tabs
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=6)
        self._nb = nb
        nb.bind("<<NotebookTabChanged>>", self._on_tab_change)

        # Dynamically add tabs from module registry
        for mod in load_registry().values():
            self._add_tab_for_module(nb, mod.id, mod.module, mod.label)

        # App-wide (i18n) settings
        self._add_tab_for_module(nb, "app", "core.i18n", T("app_settings"))

        # Config tab for admins
        if self._is_admin:
            cfg_tab = ConfigSettingsTab(nb)
            nb.add(cfg_tab, text=T("config"))

        # Buttons
        btn_row = ttk.Frame(self)
        btn_row.pack(pady=(4, 6))

        self._save_btn = ttk.Button(btn_row, text=T("save"), command=self._save_all)
        self._save_btn.pack(side="left", padx=4)

        if self._is_admin:
            self._dict_btn = ttk.Button(
                btn_row,
                text=T("main_dictionary"),  # de: Dict ergänzen / en: Fill Dict
                command=self._open_dict_editor,
            )
            self._dict_btn.pack(side="left", padx=4)
        else:
            self._dict_btn = None

    # --------------------------------------------------------------------- #
    #  Tab building helpers
    # --------------------------------------------------------------------- #
    def _add_tab_for_module(self, nb: ttk.Notebook, mod_id: str,
                            mod_module: str, label: str) -> None:
        schema = self._discover_schema(mod_module)
        if not schema:
            return

        tab = ttk.Frame(nb)
        nb.add(tab, text=label)
        self._build_module_tab(tab, mod_id, schema)

    def _build_module_tab(self, tab: ttk.Frame, module_id: str,
                          schema: list[dict]):
        for row, meta in enumerate(schema):
            scope = meta.get("scope", "both")
            if scope == "global" and not self._is_admin:
                continue

            ttk.Label(tab, text=meta["label"]).grid(
                row=row, column=0, sticky="w", padx=(4, 12), pady=4
            )

            val = self.sm.get(
                module_id, meta["key"],
                user_specific=(scope != "global"),
                default=meta.get("default"),
            )

            # Select widget type
            var: tk.Variable
            if meta["type"] == "bool":
                var = tk.BooleanVar(value=bool(val))
                widget = ttk.Checkbutton(tab, variable=var)
            elif meta["type"] == "enum":
                var = tk.StringVar(value=str(val))
                widget = ttk.Combobox(
                    tab, state="readonly",
                    values=meta["options"],
                    textvariable=var,
                    width=max(len(o) for o in meta["options"]) + 2,
                )
            else:
                var = tk.StringVar(value=str(val))
                widget = ttk.Entry(tab, textvariable=var, width=24)

            widget.grid(row=row, column=1, sticky="w")

            if scope == "global" and not self._is_admin:
                widget.state(["disabled"])

            # Store meta information for later save
            meta["_module"] = module_id
            meta["_scope"] = scope
            self._fields.append((meta, var))

    # --------------------------------------------------------------------- #
    #  Actions
    # --------------------------------------------------------------------- #
    def _save_all(self):
        try:
            for meta, var in self._fields:
                scope = meta["_scope"]
                self.sm.set(
                    meta["_module"],
                    meta["key"],
                    var.get(),
                    user_specific=(scope != "global"),
                )
            AppContext.update_language()
            messagebox.showinfo(T("success"), T("profile_saved"), parent=self)
        except Exception as exc:
            messagebox.showerror("Save error", str(exc), parent=self)

    def _open_dict_editor(self):
        try:
            from core.i18n.fill_dictionary_view import FillDictionaryView
            FillDictionaryView(self)
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self)

    # --------------------------------------------------------------------- #
    #  Helpers
    # --------------------------------------------------------------------- #
    @staticmethod
    def _discover_schema(module_path: str) -> list[dict] | None:
        try:
            module = importlib.import_module(module_path)
            return getattr(module, "SETTINGS_SCHEMA", None)
        except ModuleNotFoundError:
            return None

    def _on_tab_change(self, _event):
        sel_tab = self._nb.select()
        sel_widget = self._nb.nametowidget(sel_tab)
        from core.config.gui.config_settings_view import ConfigSettingsTab

        show = not isinstance(sel_widget, ConfigSettingsTab)

        if self._save_btn:
            self._save_btn.pack_forget()
        if self._dict_btn:
            self._dict_btn.pack_forget()

        if show:
            if self._save_btn:
                self._save_btn.pack(side="left", padx=4)
            if self._dict_btn and self._is_admin:
                self._dict_btn.pack(side="left", padx=4)
