"""
core/settings/gui/modules_config_tab.py
=======================================

Admin-Tab »Module Mgmt«

• Ein Tooltip zur Zeit, verschwindet nach 500 ms Idle oder Klick
• Vollautomatisches MODULE_META-Parsing (Version, Settings-Flag …)
• Versionsvergleich + Overwrite-Prompt
• Logger-Events bei Import / Save / Fehler
"""

from __future__ import annotations

import importlib
import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core.common.app_context import T
from core.common.module_descriptor import ModuleDescriptor
from core.common.module_registry import invalidate_registry_cache
from core.common.module_repository import ModuleRepository
from core.logging.logic.logger import logger

ROLES = ["Admin", "QMB", "User"]

# --------------------------------------------------------------------------- #
#  Tooltip-Manager (Singleton)                                                #
# --------------------------------------------------------------------------- #
class _TooltipManager:
    _instance: "_TooltipManager | None" = None

    def __new__(cls):  # noqa: D401
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.tip = None
        return cls._instance

    def show(self, widget: tk.Widget, text: str) -> None:
        self.hide()
        x, y = widget.winfo_rootx() + 20, widget.winfo_rooty() + widget.winfo_height() + 5
        self.tip = tw = tk.Toplevel(widget)
        tw.overrideredirect(True)
        tw.geometry(f"+{x}+{y}")
        tk.Label(
            tw,
            text=text,
            background="#ffffe0",
            borderwidth=1,
            relief="solid",
            wraplength=300,
            justify="left",
        ).pack(ipadx=5, ipady=3)

    def hide(self) -> None:
        if self.tip:
            self.tip.destroy()
            self.tip = None


TM = _TooltipManager()


def _tip(widget: tk.Widget, text: str) -> None:
    widget.bind(
        "<Enter>",
        lambda e: e.widget.after(
            300,
            lambda w=e.widget: TM.show(w, text) if w == widget else None,
        ),
    )
    widget.bind("<Leave>", lambda _e: TM.hide())
    widget.winfo_toplevel().bind("<Button>", lambda _e: TM.hide(), add="+")  # Klick überall


# --------------------------------------------------------------------------- #
#  Add-Dialog                                                                 #
# --------------------------------------------------------------------------- #
class _AddDialog(tk.Toplevel):
    TOOL = {
        "id": "Eindeutiger Slug (a-z,0-9,_)",
        "label": "Anzeigename im Menü",
        "module_path": "Import-Pfad der View-Datei",
        "class_name": "GUI-Klasse (tk.Frame/ttk.Frame)",
        "version": "SemVer (z. B. 1.0.1)",
        "sort_order": "Menüposition (klein = links)",
        "file_btn": "Python-Datei wählen ⇒ MODULE_META wird gelesen",
    }
    P_KEYS = ("id", "label", "module_path", "class_name", "version", "sort_order")

    def __init__(self, parent: tk.Widget, repo: ModuleRepository):
        super().__init__(parent)
        self.title("Add Module")
        self.repo = repo
        self.grab_set()
        self.resizable(False, False)

        # ---------- Eingabemaske ---------------------------------------
        frm = ttk.Frame(self, padding=10)
        frm.pack()
        self.e: dict[str, tk.Entry] = {}
        rows = [
            ("ID", "id"),
            ("Label", "label"),
            ("Import-Pfad", "module_path"),
            ("Klassenname", "class_name"),
            ("Version", "version"),
            ("Sort-Order", "sort_order"),
        ]
        for i, (lbl, key) in enumerate(rows):
            ttk.Label(frm, text=lbl).grid(row=i, column=0, sticky="w", pady=3)
            ent = ttk.Entry(frm, width=38)
            ent.grid(row=i, column=1, pady=3)
            self.e[key] = ent
            _tip(ent, self.TOOL[key])
        self.e["sort_order"].insert(0, "999")

        btn = ttk.Button(frm, text="…", width=3, command=self._choose_file)
        btn.grid(row=2, column=2, padx=4)
        _tip(btn, self.TOOL["file_btn"])

        br = ttk.Frame(self)
        br.pack(pady=6)
        ttk.Button(br, text="Cancel", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(br, text="Add", command=self._add).pack(side="right", padx=4)

        self._meta: dict | None = None

    # ---------- Datei wählen + MODULE_META lesen -----------------------
    def _choose_file(self) -> None:
        path = filedialog.askopenfilename(title="*.py", filetypes=[("Python", "*.py")])
        if not path:
            return

        full_name = self._rel_import(Path(path))
        if not full_name:
            return

        try:
            spec = importlib.util.spec_from_file_location(full_name, path)
            mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            sys.modules[full_name] = mod  # Parent-Paket sicherstellen
            spec.loader.exec_module(mod)  # type: ignore[assignment]
        except Exception as exc:
            TM.hide()
            messagebox.showerror("Import error", str(exc), parent=self)
            logger.log("ModuleMgmt", "ImportError", message=str(exc))
            return

        meta: dict | None = getattr(mod, "MODULE_META", None)
        if not meta:
            messagebox.showinfo("Info", "MODULE_META fehlt – bitte Felder ausfüllen.", parent=self)
            self._fill_manual(full_name)
            return

        # Pflicht-Felder prüfen
        for k in ("id", "label", "class", "version"):
            if k not in meta:
                messagebox.showerror("META error", f"Feld '{k}' fehlt.", parent=self)
                return

        cls = getattr(mod, meta["class"], None)
        if cls is None or not issubclass(cls, (tk.Frame, ttk.Frame)):
            messagebox.showerror("META error", "class ist nicht tk.Frame-basiert.", parent=self)
            return

        self._meta = meta
        defaults = {
            "module_path": full_name,
            "sort_order": str(meta.get("sort_order", 999)),
        }
        for k in self.P_KEYS:
            value = meta.get(k, defaults.get(k))
            self.e[k].config(state="normal")
            self.e[k].delete(0, tk.END)
            if value is not None:
                self.e[k].insert(0, value)
                self.e[k].config(state="readonly")

    def _rel_import(self, file: Path) -> str | None:
        try:
            root = Path(__file__).resolve().parents[3]
            return ".".join(file.resolve().relative_to(root).with_suffix("").parts)
        except ValueError:
            messagebox.showwarning("Path", "Datei muss im Projekt liegen.", parent=self)
            return None

    def _fill_manual(self, mod_path: str) -> None:
        for ent in self.e.values():
            ent.config(state="normal")
        self.e["module_path"].delete(0, tk.END)
        self.e["module_path"].insert(0, mod_path)

    # ---------- Add / Persistenz --------------------------------------
    def _add(self) -> None:
        data = {k: self.e[k].get().strip() for k in self.P_KEYS}
        if not all(data.values()):
            messagebox.showerror("Input", "Alle Felder müssen gefüllt sein.", parent=self)
            return

        existing = self.repo.get_by_id(data["id"])
        new_ver = self._meta["version"] if self._meta else data["version"]
        if existing and existing.version != new_ver:
            if not messagebox.askyesno(
                "Overwrite?",
                f"Installierte Version: {existing.version}\nNeue Version: {new_ver}\n\nÜberschreiben?",
                parent=self,
            ):
                return
        elif existing and existing.version == new_ver:
            messagebox.showinfo("Info", "Gleiche Version bereits registriert.", parent=self)
            return

        # Finaler Import-Check
        try:
            mod = importlib.import_module(data["module_path"])
            cls = getattr(mod, data["class_name"])
            assert issubclass(cls, (tk.Frame, ttk.Frame))
        except Exception as exc:
            messagebox.showerror("Import error", str(exc), parent=self)
            logger.log("ModuleMgmt", "FinalImportError", message=str(exc))
            return

        meta = self._meta or {}
        desc = ModuleDescriptor(
            id=data["id"],
            label=data["label"],
            module_path=data["module_path"],
            class_name=data["class_name"],
            version=new_ver,
            enabled=1,
            is_core=0,
            sort_order=int(data["sort_order"]),
            visible_for=json.dumps(meta.get("visible_for", ["Admin", "QMB", "User"])),
            settings_for=json.dumps(meta.get("settings_for", ["Admin"])),
            requires_login=1,
            permissions=None,
        )
        self.repo.upsert(desc)
        invalidate_registry_cache()
        logger.log("ModuleMgmt", "AddModule", message=f"{desc.id}:{desc.version}")
        self.destroy()


# --------------------------------------------------------------------------- #
#  Tabellen-Zeile                                                             #
# --------------------------------------------------------------------------- #
class _RowWidgets:
    """Kapselt die Widgets einer Zeile in der Module-Tabelle."""

    def __init__(self, parent: ttk.Frame, row: int, desc: ModuleDescriptor):
        self.desc = desc

        self.var_enabled = tk.BooleanVar(value=bool(desc.enabled))
        ttk.Checkbutton(parent, variable=self.var_enabled).grid(row=row, column=0, padx=4, pady=2)

        ttk.Label(parent, text=f"{desc.label}  (v{desc.version})").grid(
            row=row, column=1, sticky="w", padx=4, pady=2
        )

        self.var_sort = tk.IntVar(value=desc.sort_order)
        ttk.Spinbox(parent, from_=1, to=999, textvariable=self.var_sort, width=5).grid(
            row=row, column=2, padx=4, pady=2
        )

        self.var_vis = {r: tk.BooleanVar(value=r in json.loads(desc.visible_for)) for r in ROLES}
        self.var_set = {r: tk.BooleanVar(value=r in json.loads(desc.settings_for)) for r in ROLES}

        for col, role in enumerate(ROLES, start=3):
            ttk.Checkbutton(parent, variable=self.var_vis[role]).grid(row=row, column=col, pady=2)
        for col, role in enumerate(ROLES, start=6):
            ttk.Checkbutton(parent, variable=self.var_set[role]).grid(row=row, column=col, pady=2)

        if desc.is_core:
            self.var_enabled.set(True)
            parent.grid_slaves(row=row, column=0)[0].state(["disabled"])

    def to_descriptor(self) -> ModuleDescriptor:
        vis = [r for r, v in self.var_vis.items() if v.get()]
        stg = [r for r, v in self.var_set.items() if v.get()]
        return ModuleDescriptor(
            id=self.desc.id,
            label=self.desc.label,
            module_path=self.desc.module_path,
            class_name=self.desc.class_name,
            version=self.desc.version,
            enabled=int(self.var_enabled.get()),
            is_core=self.desc.is_core,
            sort_order=int(self.var_sort.get()),
            visible_for=json.dumps(vis or ["Admin"]),
            settings_for=json.dumps(stg or ["Admin"]),
            requires_login=self.desc.requires_login,
            permissions=self.desc.permissions,
        )


# --------------------------------------------------------------------------- #
#  Haupt-Tab                                                                  #
# --------------------------------------------------------------------------- #
class ModulesConfigTab(ttk.Frame):
    """Verwaltung aller Module (Enable / Sort / Sichtbarkeit)."""

    def __init__(self, parent: ttk.Notebook):
        super().__init__(parent)
        self.repo = ModuleRepository()
        self._rows: list[_RowWidgets] = []

        # ---------- Scroll-Canvas
        canvas = tk.Canvas(self, borderwidth=0)
        inner = ttk.Frame(canvas)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # ---------- Überschriften (zweizeilig)
        ttk.Label(inner, text="").grid(row=0, column=0, columnspan=3)
        ttk.Label(inner, text="Tab visible for").grid(row=0, column=3, columnspan=3)
        ttk.Label(inner, text="Settings visible for").grid(row=0, column=6, columnspan=3)

        hdr = ["", "Label", "Sort", *ROLES, *ROLES]
        for col, text in enumerate(hdr):
            ttk.Label(inner, text=text, style="Heading.TLabel").grid(row=1, column=col, padx=4, pady=4)

        self._reload_rows(inner)

        # ---------- Button-Leiste
        br = ttk.Frame(self)
        br.pack(fill="x", pady=8)
        ttk.Button(br, text="Add Module…", command=lambda: self._open_add(inner)).pack(
            side="left", padx=6
        )
        ttk.Button(br, text=T("Cancel"), command=lambda: self._reload_rows(inner)).pack(
            side="right", padx=6
        )
        ttk.Button(br, text=T("Save"), command=self._save).pack(side="right", padx=6)

    # ..................................................................
    def _reload_rows(self, inner: ttk.Frame) -> None:
        for w in inner.grid_slaves():
            if int(w.grid_info()["row"]) >= 2:
                w.destroy()
        self._rows.clear()
        for idx, desc in enumerate(self.repo.all_modules(), start=2):
            self._rows.append(_RowWidgets(inner, idx, desc))

    def _open_add(self, inner: ttk.Frame) -> None:
        _AddDialog(self, self.repo)
        self._reload_rows(inner)

    def _save(self) -> None:
        invalid = [r.desc.label for r in self._rows if r.to_descriptor().safe_load_class() is None]
        if invalid:
            messagebox.showerror("Validation", "Import-Fehler:\n" + "\n".join(invalid), parent=self)
            logger.log("ModuleMgmt", "ValidateFailed", message=str(invalid))
            return

        for row in self._rows:
            self.repo.upsert(row.to_descriptor())

        invalidate_registry_cache()
        logger.log("ModuleMgmt", "SavedByAdmin")
        messagebox.showinfo("Modules saved", "Änderungen gespeichert.", parent=self)
