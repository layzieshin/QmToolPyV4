"""
AssignRolesDialog – select per-document assignees for AUTHOR/REVIEWER/APPROVER.

users: list of dicts with {id, username, email, full_name}
current: {"AUTHOR": [ids], "REVIEWER": [ids], "APPROVER": [ids]}
result: same shape (usernames preferred if available, else id)
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional


class AssignRolesDialog(tk.Toplevel):
    ROLES = ("AUTHOR", "REVIEWER", "APPROVER")

    def __init__(self, parent: tk.Misc, *, users: List[dict], current: Dict[str, List[str]]) -> None:
        super().__init__(parent)
        self.title("Rollen zuweisen")
        self.resizable(True, True)
        self.result: Optional[Dict[str, List[str]]] = None
        self._users = users
        self._current = {k: set(current.get(k, [])) for k in self.ROLES}

        frm = ttk.Frame(self, padding=10); frm.grid(sticky="nsew")
        self.columnconfigure(0, weight=1); self.rowconfigure(0, weight=1)

        self._trees: Dict[str, ttk.Treeview] = {}

        for col, role in enumerate(self.ROLES):
            f = ttk.Frame(frm); f.grid(row=0, column=col, sticky="nsew", padx=6)
            ttk.Label(f, text=role).grid(row=0, column=0, sticky="w")
            tree = ttk.Treeview(f, columns=("user","sel"), show="headings", height=14, selectmode="none")
            tree.heading("user", text="User")
            tree.heading("sel", text="✓")
            tree.column("user", width=200, stretch=True)
            tree.column("sel", width=30, anchor="center")
            tree.grid(row=1, column=0, sticky="nsew")
            f.rowconfigure(1, weight=1)
            self._trees[role] = tree

            # fill rows
            for u in self._users:
                ident = u.get("username") or u.get("email") or str(u.get("id"))
                label = (u.get("full_name") or "") + f" ({ident})" if u.get("full_name") else ident
                checked = "X" if ident in self._current[role] else ""
                tree.insert("", "end", iid=f"{role}:{ident}", values=(label, checked))
            tree.bind("<Button-1>", self._toggle)

        btns = ttk.Frame(frm); btns.grid(row=1, column=0, columnspan=3, sticky="e", pady=(8,0))
        ttk.Button(btns, text="OK", command=self._ok).grid(row=0, column=0, padx=(0,6))
        ttk.Button(btns, text="Abbrechen", command=self.destroy).grid(row=0, column=1)

    def _toggle(self, event) -> None:
        tree: ttk.Treeview = event.widget  # type: ignore
        sel = tree.identify_row(event.y)
        if not sel:
            return
        role, ident = sel.split(":", 1)
        vals = list(tree.item(sel, "values"))
        if vals[1]:
            vals[1] = ""
            self._current[role].discard(ident)
        else:
            vals[1] = "X"
            self._current[role].add(ident)
        tree.item(sel, values=tuple(vals))

    def _ok(self) -> None:
        self.result = {k: sorted(v) for k, v in self._current.items()}
        self.destroy()
