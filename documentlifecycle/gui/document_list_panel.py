"""
===============================================================================
DocumentListPanel – left side document list (Treeview)
-------------------------------------------------------------------------------
Fixes:
- Grid weights + sticky NSEW → Treeview füllt den verfügbaren Platz.
- Keine feste 'height' für Treeview → volle Höhe möglich.
===============================================================================
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional, Any


class DocumentListPanel(ttk.Frame):
    def __init__(self, parent: tk.Widget, controller: Optional[Any] = None) -> None:
        super().__init__(parent)
        self._controller = controller

        # Layout: allow growth
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(self, columns=("title", "status", "updated"), show="headings")
        self.tree.heading("title", text="Title")
        self.tree.heading("status", text="Status")
        self.tree.heading("updated", text="Updated")
        self.tree.column("title", width=260, anchor="w")
        self.tree.column("status", width=100, anchor="center")
        self.tree.column("updated", width=110, anchor="center")

        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        self.tree.bind("<<TreeviewSelect>>", self._on_select)

    # wiring
    def set_controller(self, controller: Any) -> None:
        self._controller = controller

    def attach_controller(self, controller: Any) -> None:
        self._controller = controller

    # data rendering
    def render_rows(self, rows: list[dict]) -> None:
        self.tree.delete(*self.tree.get_children())
        for row in (rows or []):
            doc_id = row.get("id")
            title = row.get("title") or ""
            status = row.get("status") or ""
            updated = row.get("updated") or ""
            self.tree.insert("", "end", iid=str(doc_id), values=(title, status, updated))

    # events
    def _on_select(self, _event=None) -> None:
        sel = self.tree.selection()
        if not sel or not self._controller:
            return
        try:
            self._controller.on_select_document(int(sel[0]))
        except Exception:
            pass
