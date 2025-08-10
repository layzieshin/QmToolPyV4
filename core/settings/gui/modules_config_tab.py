"""
core/settings/gui/modules_config_tab.py
=======================================

Admin-Tab zur Modulverwaltung:
• Import via Ordner / meta.json
• Versionsvergleich + Overwrite
• Sichtbarkeit / Sortierung / Enable
• Scan-Button: Auto-Discovery on demand
• Anzeige Lizenzpflicht
"""

from __future__ import annotations

import importlib
import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import List

from core.common.module_descriptor import ModuleDescriptor
from core.common.module_registry import invalidate_registry_cache
from core.common.module_repository import ModuleRepository
from core.common.module_auto_discovery import default_roots
from core.logging.logic.logger import logger

ROLES = ["Admin", "QMB", "User"]


class _AddDialog(tk.Toplevel):
    """
    Dialog zum Hinzufügen via meta.json oder Ordner.
    """
    def __init__(self, parent: tk.Widget, repo: ModuleRepository):
        super().__init__(parent)
        self.title("Add Module from meta.json")
        self.repo = repo
        self.grab_set()
        self.resizable(False, False)

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        self._path_var = tk.StringVar()
        ttk.Label(frm, text="Module folder or meta.json").grid(row=0, column=0, sticky="w")
        path_entry = ttk.Entry(frm, textvariable=self._path_var, width=50)
        path_entry.grid(row=1, column=0, sticky="we", padx=(0, 6), pady=(4, 8))
        ttk.Button(frm, text="Browse…", command=self._select).grid(row=1, column=1, sticky="e")

        self._summary = tk.Text(frm, width=60, height=9, state="disabled")
        self._summary.grid(row=2, column=0, columnspan=2, pady=(8, 0))

        btns = ttk.Frame(frm)
        btns.grid(row=3, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right", padx=6)
        ttk.Button(btns, text="Add", command=self._add).pack(side="right")

        self._desc: ModuleDescriptor | None = None

    def _select(self) -> None:
        path = filedialog.askopenfilename(
            title="Select meta.json (or choose folder)",
            filetypes=[("meta.json", "meta.json"), ("JSON", "*.json"), ("All", "*.*")],
        )
        if not path:
            folder = filedialog.askdirectory(title="Select module folder (contains meta.json)")
            if not folder:
                return
            meta = Path(folder) / "meta.json"
        else:
            p = Path(path)
            meta = p if p.name.lower() == "meta.json" else p

        if meta.is_file() and meta.name.lower() == "meta.json":
            self._load_meta(meta)
        else:
            folder = Path(meta)
            meta_file = folder / "meta.json"
            if not meta_file.exists():
                messagebox.showerror("Not found", f"No meta.json in:\n{folder}")
                return
            self._load_meta(meta_file)

    def _load_meta(self, meta_file: Path) -> None:
        try:
            desc = ModuleDescriptor.from_meta_json(meta_file)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Invalid meta.json", str(exc), parent=self)
            logger.log("ModuleMgmt", "MetaInvalid", message=str(exc))
            return

        self._desc = desc
        self._path_var.set(str(meta_file))

        info = {
            "id": desc.id,
            "label": desc.label,
            "version": desc.version,
            "main_class": desc.main_class_fq,
            "settings_class": desc.settings_class or "-",
            "sort_order": desc.sort_order,
            "visible_for": desc.visible_list,
            "settings_for": desc.settings_list,
            "license_required": bool(desc.license_required),
            "license_tag": desc.license_tag or "-",
        }
        self._summary.config(state="normal")
        self._summary.delete("1.0", "end")
        self._summary.insert("1.0", json.dumps(info, indent=2, ensure_ascii=False))
        self._summary.config(state="disabled")

    def _validate_classes(self, d: ModuleDescriptor) -> bool:
        try:
            mod = importlib.import_module(d.module_path)
            getattr(mod, d.class_name)
        except Exception as exc:
            messagebox.showerror("Import error", f"main_class failed:\n{exc}", parent=self)
            logger.log("ModuleMgmt", "ImportError", message=str(exc))
            return False

        if d.settings_class:
            try:
                pkg, cls_name = d.settings_class.rsplit(".", 1)
                smod = importlib.import_module(pkg)
                getattr(smod, cls_name)
            except Exception as exc:
                messagebox.showerror("Import error", f"settings_class failed:\n{exc}", parent=self)
                logger.log("ModuleMgmt", "ImportError", message=str(exc))
                return False

        return True

    def _add(self) -> None:
        if not self._desc:
            messagebox.showwarning("No selection", "Please select meta.json or module folder.", parent=self)
            return

        existing = self.repo.get_by_id(self._desc.id)
        if existing and existing.version != self._desc.version:
            if not messagebox.askyesno(
                "Overwrite?",
                f"{existing.id}\nInstalled: {existing.version}\nNew:      {self._desc.version}\n\nOverwrite?",
                parent=self,
            ):
                return
        elif existing and existing.version == self._desc.version:
            messagebox.showinfo("Info", "Same version already registered.", parent=self)
            return

        if not self._validate_classes(self._desc):
            return

        self.repo.upsert(self._desc)
        invalidate_registry_cache()
        logger.log("ModuleMgmt", "AddModule", message=f"{self._desc.id}:{self._desc.version}")
        messagebox.showinfo("Module added", f"{self._desc.label} (v{self._desc.version}) installed.", parent=self)
        self.destroy()


class _RowWidgets:
    def __init__(self, parent: ttk.Frame, row: int, desc: ModuleDescriptor):
        self.desc = desc
        self.var_enabled = tk.BooleanVar(value=bool(desc.enabled))
        ttk.Checkbutton(parent, variable=self.var_enabled).grid(row=row, column=0, padx=4, pady=2)

        ttk.Label(parent, text=f"{desc.label}  (v{desc.version})").grid(row=row, column=1, sticky="w")

        self.var_sort = tk.IntVar(value=desc.sort_order)
        ttk.Spinbox(parent, from_=1, to=999, textvariable=self.var_sort, width=5).grid(row=row, column=2)

        self.var_vis = {r: tk.BooleanVar(value=r in desc.visible_list) for r in ROLES}
        self.var_set = {r: tk.BooleanVar(value=r in desc.settings_list) for r in ROLES}

        for col, role in enumerate(ROLES, start=3):
            ttk.Checkbutton(parent, variable=self.var_vis[role]).grid(row=row, column=col)
        for col, role in enumerate(ROLES, start=6):
            ttk.Checkbutton(parent, variable=self.var_set[role]).grid(row=row, column=col)

        # Lizenz-Hinweis (read-only Anzeige)
        lic = "Yes" if desc.license_required else "No"
        ttk.Label(parent, text=f"License: {lic}").grid(row=row, column=9, padx=6)

        if desc.is_core:
            self.var_enabled.set(True)
            parent.grid_slaves(row=row, column=0)[0].state(["disabled"])

    def to_descriptor(self) -> ModuleDescriptor:
        vis = [r for r, v in self.var_vis.items() if v.get()]
        stg = [r for r, v in self.var_set.items() if v.get()]
        d = self.desc
        return ModuleDescriptor(
            id=d.id,
            label=d.label,
            module_path=d.module_path,
            class_name=d.class_name,
            version=d.version,
            enabled=int(self.var_enabled.get()),
            is_core=d.is_core,
            sort_order=int(self.var_sort.get()),
            visible_for=json.dumps(vis or ["Admin"]),
            settings_for=json.dumps(stg or ["Admin"]),
            requires_login=d.requires_login,
            permissions=d.permissions,
            settings_class=d.settings_class,
            meta_path=d.meta_path,
            license_required=d.license_required,
            license_tag=d.license_tag,
        )


class ModulesConfigTab(ttk.Frame):
    def __init__(self, parent: ttk.Notebook):
        super().__init__(parent)
        self.repo = ModuleRepository()
        self._rows: List[_RowWidgets] = []

        canvas = tk.Canvas(self, borderwidth=0)
        inner = ttk.Frame(canvas)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # Header
        headers = ["", "Label", "Sort", "Admin", "QMB", "User", "Admin", "QMB", "User", "License"]
        for col, text in enumerate(headers):
            ttk.Label(inner, text=text, style="Heading.TLabel").grid(row=0, column=col, padx=4, pady=4)

        self._inner = inner
        self._reload_rows()

        br = ttk.Frame(self)
        br.pack(fill="x", pady=8)
        ttk.Button(br, text="Add Module…", command=self._open_add).pack(side="left", padx=6)
        ttk.Button(br, text="Scan for Modules", command=self._scan).pack(side="left")
        ttk.Button(br, text="Save", command=self._save).pack(side="right", padx=6)
        ttk.Button(br, text="Cancel", command=self._reload_rows).pack(side="right")

    def _reload_rows(self) -> None:
        for w in self._inner.grid_slaves():
            w.destroy()
        headers = ["", "Label", "Sort", "Admin", "QMB", "User", "Admin", "QMB", "User", "License"]
        for col, text in enumerate(headers):
            ttk.Label(self._inner, text=text, style="Heading.TLabel").grid(row=0, column=col, padx=4, pady=4)
        self._rows.clear()
        for idx, desc in enumerate(self.repo.all_modules(), start=1):
            self._rows.append(_RowWidgets(self._inner, idx, desc))

    def _open_add(self) -> None:
        _AddDialog(self, self.repo)
        self._reload_rows()
        invalidate_registry_cache()

    def _scan(self) -> None:
        count = self.repo.discover_and_register(default_roots())
        invalidate_registry_cache()
        self._reload_rows()
        messagebox.showinfo("Scan", f"{count} module(s) discovered/updated.", parent=self)

    def _save(self) -> None:
        # Validierung: Klassen importierbar?
        invalid = []
        for r in self._rows:
            d = r.to_descriptor()
            if d.safe_load_class() is None:
                invalid.append(d.label)
        if invalid:
            messagebox.showerror("Validation", "Import failed:\n" + "\n".join(invalid), parent=self)
            logger.log("ModuleMgmt", "ValidateFailed", message=str(invalid))
            return

        for r in self._rows:
            self.repo.upsert(r.to_descriptor())

        invalidate_registry_cache()
        logger.log("ModuleMgmt", "SavedByAdmin")
        messagebox.showinfo("Saved", "Changes stored.", parent=self)
