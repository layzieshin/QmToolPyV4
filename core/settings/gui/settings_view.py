"""
core/settings/gui/settings_view.py
==================================

Notebook für alle Einstellungs-Tabs.

Neu:
• Wenn ModuleDescriptor.settings_class gesetzt ist:
  → Import + Instanziierung eines spezialisierten Settings-Tabs.
• Andernfalls: generische Schema-Variante (SETTINGS_SCHEMA im Modul).
• Save-Button nur in generischen Tabs (spezialisierte Tabs verwalten sich selbst).
"""

from __future__ import annotations

import importlib
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Tuple

from core.common.app_context import AppContext, T
from core.common.module_registry import load_registry
from core.config.gui.config_settings_view import ConfigSettingsTab
from core.settings.gui.modules_config_tab import ModulesConfigTab
from core.settings.logic.settings_manager import SettingsManager
from core.models.user import UserRole


class SettingsView(ttk.Frame):
    def __init__(self, parent: tk.Widget):
        super().__init__(parent)

        self.sm: SettingsManager = AppContext.settings_manager
        self._is_admin: bool = (
            AppContext.current_user and AppContext.current_user.role == UserRole.ADMIN
        )
        self._fields: List[Tuple[dict, tk.Variable]] = []

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=6, pady=6)
        self._nb.bind("<<NotebookTabChanged>>", self._on_tab_change)

        # Modul-Tabs (spezialisierte SettingsView bevorzugt)
        for desc in load_registry().values():
            self._add_module_settings(desc)

        # I18N-Tab als normales Modul "app"
        i18n_tab = self._add_tab_for_schema(
            module_id="app", module_path="core.i18n", label=T("app_settings")
        )
        if i18n_tab:
            setattr(i18n_tab, "IS_I18N", True)

        # Admin-Tabs
        if self._is_admin:
            self._nb.add(ConfigSettingsTab(self._nb), text=T("config"))
            self._nb.add(ModulesConfigTab(self._nb), text="Module Mgmt")

        # Button-Leiste
        self._btn_row = ttk.Frame(self)
        self._btn_row.pack(pady=(4, 6))

        self._save_btn = ttk.Button(self._btn_row, text=T("save"), command=self._save_all)
        self._save_btn.pack(side="left", padx=4)

        self._dict_btn: ttk.Button | None = None
        if self._is_admin:
            self._dict_btn = ttk.Button(
                self._btn_row, text=T("main_dictionary"), command=self._open_dict_editor
            )

    # ---------------- Tabs ------------------------------------------------ #
    def _add_module_settings(self, desc) -> None:
        # 1) spezialisierte SettingsView?
        if desc.settings_class and (not self._is_admin or desc.allowed_in_settings(UserRole.ADMIN)):
            try:
                pkg, cls_name = desc.settings_class.rsplit(".", 1)
                smod = importlib.import_module(pkg)
                cls = getattr(smod, cls_name)
                tab = cls(self._nb, sm=self.sm)  # SettingsTab übernimmt eigenes Save
                self._nb.add(tab, text=f"{desc.label} ⚙")
                setattr(tab, "IS_SPECIAL", True)
                return
            except Exception as exc:
                # Fallback → generisches Schema
                print(f"[WARN] Failed to load settings_class for {desc.id}: {exc}")

        # 2) Generischer Schema-Tab
        self._add_tab_for_schema(desc.id, desc.module_path, f"{desc.label} ⚙")

    def _add_tab_for_schema(self, module_id: str, module_path: str, label: str):
        schema = self._discover_schema(module_path)
        if not schema:
            return None

        tab = ttk.Frame(self._nb)
        self._nb.add(tab, text=label)
        self._build_module_tab(tab, module_id, schema)
        return tab

    def _build_module_tab(self, tab: ttk.Frame, module_id: str, schema: list[dict]):
        for row_idx, meta in enumerate(schema):
            scope = meta.get("scope", "both")
            if scope == "global" and not self._is_admin:
                continue

            ttk.Label(tab, text=meta["label"]).grid(row=row_idx, column=0, sticky="w", padx=(4, 12), pady=4)

            val = self.sm.get(
                module_id,
                meta["key"],
                user_specific=(scope != "global"),
                fallback=meta.get("default"),
            )

            if meta["type"] == "bool":
                var = tk.BooleanVar(value=bool(val))
                widget = ttk.Checkbutton(tab, variable=var)
            elif meta["type"] == "enum":
                var = tk.StringVar(value=str(val))
                widget = ttk.Combobox(tab, state="readonly", values=meta["options"], textvariable=var,
                                      width=max(len(o) for o in meta["options"]) + 2)
            else:
                var = tk.StringVar(value=str(val))
                widget = ttk.Entry(tab, textvariable=var, width=24)

            widget.grid(row=row_idx, column=1, sticky="w")

            if scope == "global" and not self._is_admin:
                widget.state(["disabled"])

            meta["_module"] = module_id
            meta["_scope"] = scope
            self._fields.append((meta, var))

    # ---------------- Actions -------------------------------------------- #
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

    # ---------------- Helpers -------------------------------------------- #
    @staticmethod
    def _discover_schema(module_path: str) -> list[dict] | None:
        try:
            mod = importlib.import_module(module_path)
            return getattr(mod, "SETTINGS_SCHEMA", None)
        except ModuleNotFoundError:
            return None

    def _on_tab_change(self, _event) -> None:
        sel_tab = self._nb.nametowidget(self._nb.select())

        # Save-Button nur bei generischen Tabs (Spezial-Tabs speichern selbst)
        show_save = not isinstance(sel_tab, (ConfigSettingsTab, ModulesConfigTab)) \
                    and not getattr(sel_tab, "IS_SPECIAL", False)
        if show_save:
            self._save_btn.pack(side="left", padx=4)
        else:
            self._save_btn.pack_forget()

        # Dictionary-Button nur im I18N-Tab
        if self._dict_btn:
            dict_visible = getattr(sel_tab, "IS_I18N", False)
            if dict_visible:
                self._dict_btn.pack(side="left", padx=4)
            else:
                self._dict_btn.pack_forget()
