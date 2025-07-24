"""
core/settings/gui/settings_view.py
==================================

Notebook für alle Einstellungs-Tabs.

Button-Leiste
-------------
• Save-Button   – nur in regulären Modul-Tabs sichtbar
• Dictionary    – nur im I18N-Tab sichtbar (Marker IS_I18N=True)
"""

from __future__ import annotations

# ----------------------------------------------------------- #
#  Imports                                                    #
# ----------------------------------------------------------- #
import importlib
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List, Tuple

from core.common.app_context import AppContext, T
from core.settings.logic.settings_manager import SettingsManager
from core.common.module_registry import load_registry
from core.config.gui.config_settings_view import ConfigSettingsTab
from core.settings.gui.modules_config_tab import ModulesConfigTab
from core.models.user import UserRole


# ----------------------------------------------------------- #
#  SettingsView                                               #
# ----------------------------------------------------------- #
class SettingsView(ttk.Frame):
    """Root-View für *alle* Einstellungs-Tabs."""

    # ----------------------------------------------------- Konstruktor ----
    def __init__(self, parent: tk.Widget):
        super().__init__(parent)

        self.sm: SettingsManager = AppContext.settings_manager
        self._is_admin: bool = (
            AppContext.current_user
            and AppContext.current_user.role == UserRole.ADMIN
        )
        self._fields: List[Tuple[dict, tk.Variable]] = []

        # Notebook
        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=6, pady=6)
        self._nb.bind("<<NotebookTabChanged>>", self._on_tab_change)

        # Dynamische Modul-Tabs
        for mod in load_registry().values():
            self._add_tab_for_module(self._nb, mod.id, mod.module_path, mod.label)

        # I18N-Sprach-Tab
        i18n_tab = self._add_tab_for_module(
            self._nb, "app", "core.i18n", T("app_settings")
        )
        if i18n_tab:
            setattr(i18n_tab, "IS_I18N", True)  # Marker für Button-Logik

        # Admin-Tabs
        if self._is_admin:
            self._nb.add(ConfigSettingsTab(self._nb), text=T("config"))
            self._nb.add(ModulesConfigTab(self._nb), text="Module Mgmt")

        # Button-Leiste
        self._btn_row = ttk.Frame(self)
        self._btn_row.pack(pady=(4, 6))

        self._save_btn = ttk.Button(
            self._btn_row, text=T("save"), command=self._save_all
        )
        self._save_btn.pack(side="left", padx=4)

        self._dict_btn: ttk.Button | None = None
        if self._is_admin:
            self._dict_btn = ttk.Button(
                self._btn_row,
                text=T("main_dictionary"),
                command=self._open_dict_editor,
            )
            # erst beim passenden Tab einblenden

    # --------------------------------------------------- Tab-Erzeugung -----
    def _add_tab_for_module(
        self, nb: ttk.Notebook, mod_id: str, mod_path: str, label: str
    ) -> ttk.Frame | None:
        schema = self._discover_schema(mod_path)
        if not schema:
            return None

        tab = ttk.Frame(nb)
        nb.add(tab, text=label)
        self._build_module_tab(tab, mod_id, schema)
        return tab

    def _build_module_tab(
        self, tab: ttk.Frame, module_id: str, schema: list[dict]
    ):
        for row_idx, meta in enumerate(schema):
            scope = meta.get("scope", "both")
            if scope == "global" and not self._is_admin:
                continue

            ttk.Label(tab, text=meta["label"]).grid(
                row=row_idx, column=0, sticky="w", padx=(4, 12), pady=4
            )

            val = self.sm.get(
                module_id,
                meta["key"],
                user_specific=(scope != "global"),
                default=meta.get("default"),
            )

            # Widget nach Typ
            var: tk.Variable
            if meta["type"] == "bool":
                var = tk.BooleanVar(value=bool(val))
                widget = ttk.Checkbutton(tab, variable=var)
            elif meta["type"] == "enum":
                var = tk.StringVar(value=str(val))
                widget = ttk.Combobox(
                    tab,
                    state="readonly",
                    values=meta["options"],
                    textvariable=var,
                    width=max(len(o) for o in meta["options"]) + 2,
                )
            else:
                var = tk.StringVar(value=str(val))
                widget = ttk.Entry(tab, textvariable=var, width=24)

            widget.grid(row=row_idx, column=1, sticky="w")

            if scope == "global" and not self._is_admin:
                widget.state(["disabled"])

            meta["_module"] = module_id
            meta["_scope"] = scope
            self._fields.append((meta, var))

    # --------------------------------------------------- Actions ----------
    def _save_all(self) -> None:
        try:
            for meta, var in self._fields:
                self.sm.set(
                    meta["_module"],
                    meta["key"],
                    var.get(),
                    user_specific=(meta["_scope"] != "global"),
                )
            AppContext.update_language()
            messagebox.showinfo(T("success"), T("profile_saved"), parent=self)
        except Exception as exc:
            messagebox.showerror("Save error", str(exc), parent=self)

    def _open_dict_editor(self) -> None:
        try:
            from core.i18n.fill_dictionary_view import FillDictionaryView

            FillDictionaryView(self)
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self)

    # --------------------------------------------------- Helpers ----------
    @staticmethod
    def _discover_schema(module_path: str) -> list[dict] | None:
        try:
            mod = importlib.import_module(module_path)
            return getattr(mod, "SETTINGS_SCHEMA", None)
        except ModuleNotFoundError:
            return None

    def _on_tab_change(self, _event) -> None:
        """Steuert Sichtbarkeit der Button-Leiste nach Tab-Typ."""
        sel_tab = self._nb.nametowidget(self._nb.select())

        # 1) Save-Button: nur in Modul-Tabs
        save_visible = not isinstance(
            sel_tab, (ConfigSettingsTab, ModulesConfigTab)
        )
        if save_visible:
            self._save_btn.pack(side="left", padx=4)
        else:
            self._save_btn.pack_forget()

        # 2) Dictionary-Button: nur im I18N-Tab
        if self._dict_btn:
            dict_visible = getattr(sel_tab, "IS_I18N", False)
            if dict_visible:
                self._dict_btn.pack(side="left", padx=4)
            else:
                self._dict_btn.pack_forget()
