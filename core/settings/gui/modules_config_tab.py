"""
core/settings/gui/modules_config_tab.py
=======================================

Admin-Tab »Module Mgmt«

• zweizeiliger Gruppen-Header:
      ┌──────── Tab visible for ───────┐┌─── Settings visible for ───┐
Label Sort  A   Q   U                  A   Q   U
• Aktivieren, Sort-Order, Rollen-Sichtbarkeit
• Validate & Save in ModuleRepository
"""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import ttk, messagebox

from core.common.module_repository import ModuleRepository
from core.common.module_descriptor import ModuleDescriptor
from core.common.module_registry import invalidate_registry_cache
from core.logging.logic.logger import logger
from core.common.app_context import T

ROLES = ["Admin", "QMB", "User"]


class _RowWidgets:
    """Kapselt alle Widgets einer Tabellenzeile."""

    def __init__(self, parent: ttk.Frame, row: int, desc: ModuleDescriptor):
        self.desc = desc

        # Enabled
        self.var_enabled = tk.BooleanVar(value=bool(desc.enabled))
        self.chk_enabled = ttk.Checkbutton(parent, variable=self.var_enabled)
        self.chk_enabled.grid(row=row, column=0, padx=4, pady=2)

        # Label
        ttk.Label(parent, text=desc.label).grid(
            row=row, column=1, padx=4, pady=2, sticky="w"
        )

        # Sort-Order
        self.var_sort = tk.IntVar(value=desc.sort_order)
        ttk.Spinbox(
            parent, from_=1, to=999, textvariable=self.var_sort, width=5
        ).grid(row=row, column=2, padx=4, pady=2)

        # Rollen-Checkboxen -----------------------------------------------------------------
        self.var_vis = {r: tk.BooleanVar(value=r in json.loads(desc.visible_for)) for r in ROLES}
        self.var_set = {r: tk.BooleanVar(value=r in json.loads(desc.settings_for)) for r in ROLES}

        for col, role in enumerate(ROLES, start=3):
            ttk.Checkbutton(parent, variable=self.var_vis[role]).grid(row=row, column=col, pady=2)

        for col, role in enumerate(ROLES, start=6):
            ttk.Checkbutton(parent, variable=self.var_set[role]).grid(row=row, column=col, pady=2)

        if desc.is_core:
            self.chk_enabled.state(["disabled"])

    # -------------------- Descriptor zurückbauen ---------------------------
    def to_descriptor(self) -> ModuleDescriptor:
        vis = [r for r, v in self.var_vis.items() if v.get()]
        stg = [r for r, v in self.var_set.items() if v.get()]
        return ModuleDescriptor(
            id=self.desc.id,
            label=self.desc.label,
            module_path=self.desc.module_path,
            class_name=self.desc.class_name,
            enabled=int(self.var_enabled.get()) if not self.desc.is_core else 1,
            is_core=self.desc.is_core,
            sort_order=int(self.var_sort.get()),
            visible_for=json.dumps(vis or ["Admin"]),
            settings_for=json.dumps(stg or ["Admin"]),
            requires_login=self.desc.requires_login,
            permissions=self.desc.permissions,
        )


class ModulesConfigTab(ttk.Frame):
    """Admin-Tab zur Modulverwaltung."""

    def __init__(self, parent: ttk.Notebook):
        super().__init__(parent)

        self.repo = ModuleRepository()
        self.rows: list[_RowWidgets] = []

        # ---------- Scroll-Canvas -----------------------------------------
        canvas = tk.Canvas(self, borderwidth=0)
        inner = ttk.Frame(canvas)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)

        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # ---------- Header Zeile 0 (Gruppenbeschriftungen) ----------------
        ttk.Label(inner, text="").grid(row=0, column=0)          # Platzhalter
        ttk.Label(inner, text="").grid(row=0, column=1)
        ttk.Label(inner, text="").grid(row=0, column=2)

        ttk.Label(inner, text="Tab visible for").grid(row=0, column=3, columnspan=3, pady=(0, 2))
        ttk.Label(inner, text="Settings visible for").grid(row=0, column=6, columnspan=3, pady=(0, 2))

        # ---------- Header Zeile 1 (Spaltenüberschriften) -----------------
        headers = ["", "Label", "Sort", *ROLES, *ROLES]
        for col, txt in enumerate(headers):
            ttk.Label(inner, text=txt, style="Heading.TLabel").grid(
                row=1, column=col, padx=4, pady=(0, 4)
            )

        # ---------- Datenzeilen ------------------------------------------
        for r, desc in enumerate(self.repo.all_modules(), start=2):
            self.rows.append(_RowWidgets(inner, r, desc))

        # ---------- Buttons ----------------------------------------------
        btn_row = ttk.Frame(self)
        btn_row.pack(fill="x", pady=8)
        ttk.Button(btn_row, text=T("Save"), command=self._save).pack(side="right", padx=6)
        ttk.Button(btn_row, text=T("Cancel"), command=self._reload).pack(side="right", padx=6)

    # ----------------------- Aktionen ------------------------------------
    def _reload(self) -> None:
        """Verwirft Änderungen und lädt Tabelle neu."""
        for r in self.rows:
            r.chk_enabled.master.destroy()
        self.rows.clear()
        for idx, desc in enumerate(self.repo.all_modules(), start=2):
            self.rows.append(_RowWidgets(self.winfo_children()[0], idx, desc))

    def _save(self) -> None:
        failed: list[str] = []
        for row in self.rows:
            if row.to_descriptor().safe_load_class() is None:
                failed.append(row.desc.label)

        if failed:
            messagebox.showerror("Validation error", "\n".join(failed), parent=self)
            logger.log("ModuleMgmt", "ValidateFailed", message=str(failed))
            return

        for row in self.rows:
            self.repo.upsert(row.to_descriptor())

        invalidate_registry_cache()
        logger.log("ModuleMgmt", "SavedByAdmin")
        messagebox.showinfo(
            "Modules saved",
            "Changes stored.\nRestart the application or reload navigation.",
            parent=self,
        )
