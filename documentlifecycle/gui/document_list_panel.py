"""
Left list panel – pure UI. Notifies controller on selection.
"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk


class DocumentListPanel(ttk.Frame):
    def __init__(self, parent: tk.Widget, controller, **_ignore):
        super().__init__(parent)
        self._controller = controller

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(self, columns=("title", "status", "updated"),
                                 show="headings", selectmode="browse")
        self.tree.heading("title", text="Title")
        self.tree.heading("status", text="Status")
        self.tree.heading("updated", text="Updated")
        self.tree.column("title", width=260, anchor="w")
        self.tree.column("status", width=110, anchor="center")
        self.tree.column("updated", width=120, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")

        yscroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        yscroll.grid(row=0, column=1, sticky="ns")

        self.tree.bind("<<TreeviewSelect>>", self._on_select)

    def attach_controller(self, controller) -> None:
        self._controller = controller

    def render_rows(self, rows: list[dict]) -> None:
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            self.tree.insert("", "end", iid=str(row["id"]),
                             values=(row["title"], row["status"], row["updated"]))

    def _on_select(self, _evt=None):
        sel = self.tree.selection()
        if not sel or not self._controller:
            return
        self._controller.on_select_document(int(sel[0]))
