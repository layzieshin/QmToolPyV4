"""
AssignRolesDialog – select per-document assignees for AUTHOR/REVIEWER/APPROVER.

Users are shown in three columns (one per role). A click toggles selection.
Result format mirrors the input shape (sorted identifiers).

Internationalization:
- All UI strings use tr("…") per documents.* and common.* keys.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional

from documents.gui.i18n import tr  # same import style as in metadata_dialog.py


class AssignRolesDialog(tk.Toplevel):
    """Modal dialog to assign users to roles for a document."""

    ROLES = ("AUTHOR", "REVIEWER", "APPROVER")

    def __init__(self, parent: tk.Misc, *, users: List[dict], current: Dict[str, List[str]]) -> None:
        super().__init__(parent)

        # Window configuration
        self.title(tr("documents.assign_roles.title", "Assign roles"))
        self.resizable(True, True)
        self.result: Optional[Dict[str, List[str]]] = None

        # Data
        self._users = users
        self._current = {k: set(current.get(k, [])) for k in self.ROLES}

        # Layout root
        frm = ttk.Frame(self, padding=10)
        frm.grid(sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Translate role captions once
        role_captions = {
            "AUTHOR": tr("documents.roles.author", "Author"),
            "REVIEWER": tr("documents.roles.reviewer", "Reviewer"),
            "APPROVER": tr("documents.roles.approver", "Approver"),
        }

        # Build three trees (one per role)
        self._trees: Dict[str, ttk.Treeview] = {}

        for col, role in enumerate(self.ROLES):
            f = ttk.Frame(frm)
            f.grid(row=0, column=col, sticky="nsew", padx=6)
            # Role label
            ttk.Label(f, text=role_captions[role]).grid(row=0, column=0, sticky="w")

            # Tree
            tree = ttk.Treeview(
                f,
                columns=("user", "sel"),
                show="headings",
                height=14,
                selectmode="none",
            )
            tree.heading("user", text=tr("documents.assign_roles.col.user", "User"))
            tree.heading("sel", text=tr("documents.assign_roles.col.selected", "Selected"))
            tree.column("user", width=200, stretch=True, anchor="w")
            tree.column("sel", width=90, anchor="center", stretch=False)
            tree.grid(row=1, column=0, sticky="nsew")
            f.rowconfigure(1, weight=1)

            self._trees[role] = tree

            # Fill rows
            for u in self._users:
                ident = u.get("username") or u.get("email") or str(u.get("id"))
                full = (u.get("full_name") or "").strip()
                label = f"{full} ({ident})" if full else ident
                checked = tr("common.checkbox.checked", "X") if ident in self._current[role] else ""
                tree.insert("", "end", iid=f"{role}:{ident}", values=(label, checked))

            # Toggle on click
            tree.bind("<Button-1>", self._toggle)

        # Buttons
        btns = ttk.Frame(frm)
        btns.grid(row=1, column=0, columnspan=3, sticky="e", pady=(8, 0))
        ttk.Button(btns, text=tr("common.ok", "OK"), command=self._ok).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(btns, text=tr("common.cancel", "Cancel"), command=self.destroy).grid(row=0, column=1)

        # Make modal
        self.transient(parent)
        self.grab_set()
        self.wait_visibility()
        self.wm_attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _toggle(self, event) -> None:
        """Toggle checkmark for clicked row."""
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
            vals[1] = tr("common.checkbox.checked", "X")
            self._current[role].add(ident)
        tree.item(sel, values=tuple(vals))

    def _ok(self) -> None:
        """Finalize selection."""
        self.result = {k: sorted(v) for k, v in self._current.items()}
        self.destroy()
