"""
fill_dictionary_view.py

Admin-Editor für die zentrale translations/labels.tsv
• zeigt Missing-Keys (oder alle Keys) in einer Tabelle
• erlaubt Bearbeitung in-place
• schreibt TSV atomar zurück
"""

from __future__ import annotations

import csv
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from typing import Dict, List
from core.common.app_context import AppContext

from core.i18n.translation_manager import translations, T
from core.logging.logic.logger import logger

LABELS_FILE = translations.file_path or Path("translations/labels.tsv")
LANGS = ["de", "en"]                     # aktuell gepflegte Sprachen


class FillDictionaryView(tk.Toplevel):
    """Einfache Tabellen-GUI zum Ergänzen/Ändern der Übersetzungen."""

    def __init__(self, parent: tk.Widget):
        super().__init__(parent)
        self.title(T("core.main_dictionary"))          # „Dict ergänzen“ / „Fill Dict“
        self.geometry("900x500")
        self.transient(parent)
        self.grab_set()

        self._table = ttk.Treeview(
            self, columns=("label", *LANGS), show="headings", height=20
        )
        self._table.pack(fill="both", expand=True, padx=10, pady=10)

        # Spaltenköpfe
        self._table.heading("label", text="Label")
        for lang in LANGS:
            self._table.heading(lang, text=lang)

        self._table.column("label", width=200, anchor="w")
        for lang in LANGS:
            self._table.column(lang, width=200, anchor="w")

        self._table.bind("<Double-1>", self._on_edit_cell)

        # Buttons
        btn_row = ttk.Frame(self); btn_row.pack(pady=6)
        ttk.Button(btn_row, text=T("core.save"), command=self._save).pack(side="left", padx=5)
        ttk.Button(btn_row, text=T("core.cancel"), command=self.destroy).pack(side="left", padx=5)

        self._load_data()

    # ---------------------------- Data -------------------------------- #
    def _load_data(self):
        """Lädt Labels aus TSV und füllt Tabelle. Zeigt fehlende Keys fett."""
        data = self._read_tsv()
        missing = []          # type: List[str]
        self._table.delete(*self._table.get_children())

        for label in sorted(data.keys()):
            row = [label] + [data[label].get(lang, "") for lang in LANGS]
            if "" in row[1:]:
                missing.append(label)
            self._table.insert("", "end", values=row, tags=("missing",) if "" in row[1:] else ())

        self._table.tag_configure("missing", font=("TkDefaultFont", 10, "bold"))

        messagebox.showinfo(
            "Info",
            f"{len(missing)} fehlende Übersetzungen markiert (fett).",
            parent=self,
        )

    def _read_tsv(self) -> Dict[str, Dict[str, str]]:
        if not LABELS_FILE.exists():
            return {}
        data: Dict[str, Dict[str, str]] = {}
        with LABELS_FILE.open(encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            header = next(reader)
            col_langs = header[1:]
            for row in reader:
                if not row:
                    continue
                label = row[0]
                data[label] = {lang: (row[i+1] if i+1 < len(row) else "") for i, lang in enumerate(col_langs)}
        return data

    # ---------------------------- Editing ----------------------------- #
    def _on_edit_cell(self, event):
        item = self._table.identify_row(event.y)
        column = self._table.identify_column(event.x)
        if not item or not column:
            return

        col_index = int(column[1:]) - 1        # 0-basiert
        if col_index == 0:
            messagebox.showwarning("Warnung", "Label selbst nicht editierbar.", parent=self)
            return

        x, y, w, h = self._table.bbox(item, column)
        value = self._table.set(item, column)

        entry = tk.Entry(self._table)
        entry.place(x=x, y=y, width=w, height=h)
        entry.insert(0, value)
        entry.focus()

        def _save_edit(event=None):
            new_val = entry.get()
            self._table.set(item, column, new_val)
            entry.destroy()

        entry.bind("<Return>", _save_edit)
        entry.bind("<FocusOut>", _save_edit)

    # ---------------------------- Save -------------------------------- #
    def _save(self):
        # lese Tabelle zurück in dict
        user = AppContext.current_user
        data = {}
        for item in self._table.get_children():
            vals = self._table.item(item)["values"]
            label = vals[0]
            data[label] = {lang: vals[i+1] for i, lang in enumerate(LANGS)}

        # schreibe TSV atomar
        tmp = LABELS_FILE.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter="\t")
            writer.writerow(["label", *LANGS])
            for label in sorted(data.keys()):
                row = [label] + [data[label].get(lang, "") for lang in LANGS]
                writer.writerow(row)
        tmp.replace(LABELS_FILE)

        translations.load_file(LABELS_FILE)          # Reload in Memory
        user = AppContext.current_user
        logger.log(
            feature="Locale",
            event="DictUpdated",
            user_id=user.id if user else None,
            username=user.username if user else None,
            message="labels.tsv updated via GUI",
        )
        messagebox.showinfo("Info", "Dictionary gespeichert.", parent=self)
        self.destroy()
