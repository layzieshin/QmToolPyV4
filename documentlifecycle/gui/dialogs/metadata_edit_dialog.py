"""
===============================================================================
MetadataEditDialog – review & edit document metadata before persisting
-------------------------------------------------------------------------------
Fields:
  - Code (document identifier)
  - Title
  - Type (combobox from DocumentType)
  - Description
===============================================================================
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, Any

try:
    from core.common.app_context import T  # type: ignore
except Exception:  # pragma: no cover
    def T(key: str) -> str: return ""

from documentlifecycle.models.document_type import DocumentType


class MetadataEditDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, *, title_text: str, initial: dict[str, Any]) -> None:
        super().__init__(parent)
        self.title(title_text)
        self.transient(parent)
        self.resizable(False, False)
        self.grab_set()

        self._result: Optional[dict[str, Any]] = None

        self.var_code = tk.StringVar(value=initial.get("code") or "")
        self.var_title = tk.StringVar(value=initial.get("title") or "")
        self.var_doc_type = tk.StringVar(value=initial.get("doc_type") or "OTHER")
        self.var_desc = tk.StringVar(value=initial.get("description") or "")

        frm = ttk.Frame(self, padding=12); frm.grid(row=0, column=0, sticky="nsew")
        frm.columnconfigure(1, weight=1)

        ttk.Label(frm, text=T("field.code") or "Code").grid(row=0, column=0, sticky="w", pady=4, padx=(0, 8))
        ttk.Entry(frm, textvariable=self.var_code, width=32).grid(row=0, column=1, sticky="ew")

        ttk.Label(frm, text=T("field.title") or "Title").grid(row=1, column=0, sticky="w", pady=4, padx=(0, 8))
        ttk.Entry(frm, textvariable=self.var_title, width=48).grid(row=1, column=1, sticky="ew")

        ttk.Label(frm, text=T("field.doc_type") or "Type").grid(row=2, column=0, sticky="w", pady=4, padx=(0, 8))
        cb = ttk.Combobox(frm, textvariable=self.var_doc_type, state="readonly",
                          values=[e.value for e in DocumentType])
        cb.grid(row=2, column=1, sticky="ew")
        if self.var_doc_type.get() not in cb["values"]:
            self.var_doc_type.set("OTHER")

        ttk.Label(frm, text=T("field.description") or "Description").grid(row=3, column=0, sticky="nw", pady=4, padx=(0, 8))
        ttk.Entry(frm, textvariable=self.var_desc, width=64).grid(row=3, column=1, sticky="ew")

        btns = ttk.Frame(frm); btns.grid(row=4, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text=T("button.cancel") or "Cancel", command=self._on_cancel).grid(row=0, column=0, padx=6)
        ttk.Button(btns, text=T("button.save") or "Save", command=self._on_save).grid(row=0, column=1, padx=6)

        self.bind("<Return>", lambda _e: self._on_save())
        self.bind("<Escape>", lambda _e: self._on_cancel())

    def _on_cancel(self) -> None:
        self._result = None
        self.destroy()

    def _on_save(self) -> None:
        title = (self.var_title.get() or "").strip()
        code = (self.var_code.get() or "").strip() or None
        doc_type = (self.var_doc_type.get() or "OTHER").strip()
        description = (self.var_desc.get() or "").strip()
        if not title:
            self.bell(); return
        self._result = {"title": title, "code": code, "doc_type": doc_type, "description": description}
        self.destroy()

    def show_modal(self) -> Optional[dict[str, Any]]:
        self.wait_window(self)
        return self._result
