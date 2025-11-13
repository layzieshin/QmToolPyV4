"""
===============================================================================
SearchBar – Top-Leiste mit Suche + Import/Neu-Funktionen
-------------------------------------------------------------------------------
Responsibility
- Zeigt: [Import DOCX] [Neu aus Vorlage] | [Suchfeld] [Suchen]
- Delegiert an:
    * on_search(query) Callback (falls gesetzt) für die Suche
    * Controller (CreationController) für Import/Neu:
        - action_import_docx()
        - action_create_from_template()

Wiring
- Nutzt set_controller(...) ODER attach_controller(...).
- Gibt bei fehlendem Controller eine gut sichtbare Meldung aus.

SRP
- Rein GUI + Delegation. Keine Fach-/Speicherlogik hier drin.
===============================================================================
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional, Any

try:
    from core.common.app_context import T  # type: ignore
except Exception:  # pragma: no cover
    def T(_key: str) -> str: return ""


class SearchBar(ttk.Frame):
    """
    Top search and creation action bar.
    """

    def __init__(self, parent: tk.Widget, *, on_search: Optional[Callable[[str], None]] = None) -> None:
        super().__init__(parent)
        self._controller: Optional[Any] = None
        self._on_search = on_search

        self.columnconfigure(2, weight=1)

        # Left: creation buttons
        self._left = ttk.Frame(self)
        self._left.grid(row=0, column=0, sticky="w", padx=(0, 8))
        self._btn_import = ttk.Button(
            self._left,
            text=T("documentlifecycle.search.import_docx") or "Import DOCX",
            command=self._on_import_clicked
        )
        self._btn_import.grid(row=0, column=0, padx=(0, 6))
        self._btn_new = ttk.Button(
            self._left,
            text=T("documentlifecycle.search.new_from_template") or "New from template",
            command=self._on_new_from_template_clicked
        )
        self._btn_new.grid(row=0, column=1, padx=(0, 6))

        # Middle: search field
        self._query = tk.StringVar()
        self._entry = ttk.Entry(self, textvariable=self._query)
        self._entry.grid(row=0, column=2, sticky="ew", padx=(0, 6))
        self._entry.insert(0, T("documentlifecycle.search.placeholder") or "Search...")

        # Right: search button
        self._btn_search = ttk.Button(
            self,
            text=T("documentlifecycle.search.button") or "Search",
            command=self._submit
        )
        self._btn_search.grid(row=0, column=3, sticky="e")

    # --- wiring --------------------------------------------------------------
    def set_controller(self, controller: Any) -> None:
        """Preferred wiring method if available."""
        self._controller = controller

    def attach_controller(self, controller: Any) -> None:
        """Fallback wiring method used in anderen GUI-Teilen."""
        self._controller = controller

    # --- actions -------------------------------------------------------------
    def _submit(self) -> None:
        if callable(self._on_search):
            try:
                self._on_search(self._query.get().strip())
                return
            except Exception as exc:
                messagebox.showerror(
                    T("documentlifecycle.errors.search") or "Search error",
                    f"{type(exc).__name__}: {exc}",
                    parent=self.winfo_toplevel()
                )
                return
        messagebox.showinfo(
            T("documentlifecycle.search") or "Search",
            T("documentlifecycle.search.no_handler") or "No search handler wired.",
            parent=self.winfo_toplevel()
        )

    def _on_import_clicked(self) -> None:
        ctl = self._controller
        if not ctl or not hasattr(ctl, "action_import_docx"):
            messagebox.showwarning(
                T("documentlifecycle.search.import_docx") or "Import DOCX",
                T("documentlifecycle.search.no_controller") or "No controller connected.",
                parent=self.winfo_toplevel()
            )
            return
        try:
            getattr(ctl, "action_import_docx")()
        except Exception as exc:
            messagebox.showerror(
                T("documentlifecycle.search.import_docx") or "Import DOCX",
                f"{type(exc).__name__}: {exc}",
                parent=self.winfo_toplevel()
            )

    def _on_new_from_template_clicked(self) -> None:
        ctl = self._controller
        if not ctl or not hasattr(ctl, "action_create_from_template"):
            messagebox.showwarning(
                T("documentlifecycle.search.new_from_template") or "New from template",
                T("documentlifecycle.search.no_controller") or "No controller connected.",
                parent=self.winfo_toplevel()
            )
            return
        try:
            getattr(ctl, "action_create_from_template")()
        except Exception as exc:
            messagebox.showerror(
                T("documentlifecycle.search.new_from_template") or "New from template",
                f"{type(exc).__name__}: {exc}",
                parent=self.winfo_toplevel()
            )
