"""
settings_view.py

Zeigt alle SETTINGS_SCHEMA-Definitionen:
 • für jedes registrierte Modul
 • plus feste „System-Schemas“ (z. B. core.i18n → App-Sprache)

Enthält für Admins einen Button „Dict ergänzen / Fill Dict“,
um den Übersetzungs-Editor (fill_dictionary_view.py) zu öffnen.
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


class SettingsView(ttk.Frame):
    # ------------------------------------------------------------------ #
    # Konstruktion                                                       #
    # ------------------------------------------------------------------ #
    def __init__(self, parent):
        super().__init__(parent)

        self.sm: SettingsManager = AppContext.settings_manager
        self._is_admin = (
            AppContext.current_user
            and AppContext.current_user.role == UserRole.ADMIN
        )

        self._fields: List[Tuple[Dict, tk.Variable]] = []   # (meta, var)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=6)

        # ---------- 1) Registry-Module --------------------------------
        for mod in load_registry().values():
            self._add_tab_for_module(nb, mod.id, mod.module, mod.label)

        # ---------- 2) System-Schemas ohne GUI-Modul ------------------
        self._add_tab_for_module(nb, "app", "core.i18n", T("app_settings"))

        # ---------- Buttons unten -------------------------------------
        btn_row = ttk.Frame(self)
        btn_row.pack(pady=(4, 6))

        ttk.Button(
            btn_row,
            text=T("save"),
            command=self._save_all,
        ).pack(side="left", padx=4)

        # Admin-spezifischer Button für den Dictionary-Editor
        if self._is_admin:
            ttk.Button(
                btn_row,
                text=T("main_dictionary"),          # de: Dict ergänzen / en: Fill Dict
                command=self._open_dict_editor,
            ).pack(side="left", padx=4)

    # ------------------------------------------------------------------ #
    # Tab-Erzeugung                                                      #
    # ------------------------------------------------------------------ #
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
                continue                      # globale Settings verstecken

            ttk.Label(tab, text=meta["label"]).grid(
                row=row, column=0, sticky="w", padx=(4, 12), pady=4
            )

            # aktuellen Wert laden
            val = self.sm.get(
                module_id, meta["key"],
                user_specific=(scope != "global"),
                default=meta.get("default"),
            )

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
            else:                              # "str"
                var = tk.StringVar(value=str(val))
                widget = ttk.Entry(tab, textvariable=var, width=24)

            widget.grid(row=row, column=1, sticky="w")

            if scope == "global" and not self._is_admin:
                widget.state(["disabled"])

            meta["_module"] = module_id
            meta["_scope"] = scope
            self._fields.append((meta, var))

    # ------------------------------------------------------------------ #
    # Apply-Button                                                      #
    # ------------------------------------------------------------------ #
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
            AppContext.update_language()   # Sprache sofort anwenden
            messagebox.showinfo(T("success"), T("profile_saved"), parent=self)
        except Exception as exc:
            messagebox.showerror("Save error", str(exc), parent=self)

    # ------------------------------------------------------------------ #
    # Dictionary-Editor                                                  #
    # ------------------------------------------------------------------ #
    def _open_dict_editor(self):
        try:
            from core.i18n.fill_dictionary_view import FillDictionaryView
            FillDictionaryView(self)
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self)

    # ------------------------------------------------------------------ #
    # Helpers                                                           #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _discover_schema(module_path: str) -> list[dict] | None:
        """Importiert *module_path* und gibt dessen SETTINGS_SCHEMA zurück."""
        try:
            m = importlib.import_module(module_path)
            return getattr(m, "SETTINGS_SCHEMA", None)
        except ModuleNotFoundError:
            return None
