"""
Simple metadata editor dialog for a document.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from datetime import datetime
from typing import Optional

from documents.gui.i18n import tr
from documents.models.document_models import DocumentRecord


class MetadataDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, record: DocumentRecord, *, allowed_types: list[str]) -> None:
        super().__init__(parent)
        self.title(tr("documents.meta.title", "Edit metadata"))
        self.resizable(False, False)
        self.result: Optional[DocumentRecord] = None
        self._rec = record
        self._types = allowed_types

        frm = ttk.Frame(self, padding=12)
        frm.grid(sticky="nsew")
        self.columnconfigure(0, weight=1)

        ttk.Label(frm, text=tr("documents.meta.lbl.title", "Title")).grid(row=0, column=0, sticky="w", pady=4)
        self.e_title = ttk.Entry(frm, width=60)
        self.e_title.grid(row=0, column=1, sticky="ew", pady=4)
        self.e_title.insert(0, record.title)

        ttk.Label(frm, text=tr("documents.meta.lbl.type", "Type")).grid(row=1, column=0, sticky="w", pady=4)
        self.cb_type = ttk.Combobox(frm, values=self._types, state="readonly", width=20)
        self.cb_type.grid(row=1, column=1, sticky="w", pady=4)
        self.cb_type.set(record.doc_type if record.doc_type in self._types else (self._types[0] if self._types else ""))

        ttk.Label(frm, text=tr("documents.meta.lbl.area", "Area")).grid(row=2, column=0, sticky="w", pady=4)
        self.e_area = ttk.Entry(frm, width=30); self.e_area.grid(row=2, column=1, sticky="w", pady=4)
        if record.area: self.e_area.insert(0, record.area)

        ttk.Label(frm, text=tr("documents.meta.lbl.process", "Process")).grid(row=3, column=0, sticky="w", pady=4)
        self.e_process = ttk.Entry(frm, width=30); self.e_process.grid(row=3, column=1, sticky="w", pady=4)
        if record.process: self.e_process.insert(0, record.process)

        ttk.Label(frm, text=tr("documents.meta.lbl.nextreview", "Next review (YYYY-MM-DD)")).grid(row=4, column=0, sticky="w", pady=4)
        self.e_next = ttk.Entry(frm, width=20); self.e_next.grid(row=4, column=1, sticky="w", pady=4)
        if record.next_review:
            self.e_next.insert(0, record.next_review.date().isoformat())

        btns = ttk.Frame(frm); btns.grid(row=5, column=0, columnspan=2, sticky="e", pady=(12,0))
        ttk.Button(btns, text=tr("common.cancel", "Cancel"), command=self.destroy).grid(row=0, column=0, padx=(0,6))
        ttk.Button(btns, text=tr("common.ok", "OK"), command=self._ok).grid(row=0, column=1)

        self.transient(parent); self.grab_set(); self.e_title.focus_set()
        self.wait_visibility(); self.wm_attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _ok(self) -> None:
        title = self.e_title.get().strip() or tr("documents.untitled", "Untitled")
        doc_type = self.cb_type.get().strip() or "SOP"
        area = self.e_area.get().strip() or None
        process = self.e_process.get().strip() or None
        next_review = None
        txt = self.e_next.get().strip()
        if txt:
            try:
                next_review = datetime.fromisoformat(txt)
            except Exception:
                next_review = None
        self._rec.title = title
        self._rec.doc_type = doc_type
        self._rec.area = area
        self._rec.process = process
        self._rec.next_review = next_review
        self.result = self._rec
        self.destroy()
