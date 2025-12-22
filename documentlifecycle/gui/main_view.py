"""
===============================================================================
DocumentLifecycleView – 3-Zonen-Layout (Search | List+Details | Bottom)
-------------------------------------------------------------------------------
- SearchBar (oben)
- DocumentListPanel (links) + DocumentDetailPanel (rechts)
- BottomBar (unten)

Fixes:
- left_wrap/right_wrap mit row/column weights → volle Höhe/Breite.
===============================================================================
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Any

# Settings + i18n
try:
    from core.settings.logic.settings_manager import SettingsManager  # type: ignore
except Exception:  # pragma: no cover
    class SettingsManager:
        def get(self, *_a, **_k): return False
        def set(self, *_a, **_k): pass

try:
    from core.common.app_context import T  # type: ignore
except Exception:  # pragma: no cover
    def T(_key: str) -> str: return ""

# GUI parts
from documentlifecycle.gui.search_bar import SearchBar
from documentlifecycle.gui.document_list_panel import DocumentListPanel
from documentlifecycle.gui.detail_panel import DocumentDetailPanel
from documentlifecycle.gui.bottom_bar import BottomBar

# Controllers (new expected naming)
from documentlifecycle.controllers.topbar_controller import TopbarController
from documentlifecycle.controllers.document_list_controller import DocumentListController
from documentlifecycle.controllers.document_details_controller import DocumentDetailsController
from documentlifecycle.controllers.bottombar_controller import BottomBarController

# Services
from documentlifecycle.logic.services.document_service import DocumentService
from documentlifecycle.logic.services.document_creation_service import DocumentCreationService
from documentlifecycle.logic.services.ui_state_service import UIStateService

# Repositories (SQLite)
from documentlifecycle.logic.repository.sqlite.document_repository_sqlite import DocumentRepositorySQLite
from documentlifecycle.logic.repository.sqlite.role_repository_sqlite import RoleRepositorySQLite

# Current user provider (AppContext bridge preferred; fallback for dev)
try:
    from documentlifecycle.logic.adapters.appcontext_user_provider import AppContextUserProvider  # type: ignore
except Exception:  # pragma: no cover
    AppContextUserProvider = None  # type: ignore

from documentlifecycle.logic.adapters.current_user_provider import DefaultCurrentUserProvider


class DocumentLifecycleView(ttk.Frame):
    _FEATURE_ID = "documentlifecycle"

    def __init__(self, parent: tk.Widget, *,
                 settings_manager: Optional[SettingsManager] = None,
                 sm: Optional[SettingsManager] = None,
                 **_ignore) -> None:
        super().__init__(parent)

        # Layout base
        self._sm: SettingsManager = (settings_manager or sm) or SettingsManager()  # type: ignore
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._dev_borders_var = tk.BooleanVar(
            value=bool(self._sm.get(self._FEATURE_ID, "ui_dev_borders", False))
        )

        # TOP
        top = tk.Frame(self, highlightthickness=0, highlightbackground="#999")
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(0, weight=1)

        header = ttk.Frame(top)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        ttk.Label(
            header,
            text=T("documentlifecycle.title") or "Document Lifecycle",
            font=("Segoe UI", 15, "bold")
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))

        ttk.Checkbutton(
            header, text="Borders",
            variable=self._dev_borders_var,
            command=self._apply_dev_borders
        ).grid(row=0, column=1, sticky="e", padx=12)

        self.search_bar = SearchBar(top, on_search=self._on_search_clicked)
        self.search_bar.grid(row=1, column=0, sticky="ew", padx=12, pady=(4, 8))

        # MIDDLE
        mid = tk.Frame(self, highlightthickness=0, highlightbackground="#999")
        mid.grid(row=1, column=0, sticky="nsew")
        mid.columnconfigure(0, weight=1)
        mid.columnconfigure(1, weight=2)
        mid.rowconfigure(0, weight=1)

        left_wrap = tk.Frame(mid, highlightthickness=0, highlightbackground="#999")
        left_wrap.grid(row=0, column=0, sticky="nsew")
        left_wrap.columnconfigure(0, weight=1)
        left_wrap.rowconfigure(0, weight=1)

        right_wrap = tk.Frame(mid, highlightthickness=0, highlightbackground="#999")
        right_wrap.grid(row=0, column=1, sticky="nsew")
        right_wrap.columnconfigure(0, weight=1)
        right_wrap.rowconfigure(0, weight=1)

        self.list_panel = DocumentListPanel(left_wrap, controller=None)
        self.list_panel.grid(row=0, column=0, sticky="nsew", padx=12, pady=(0, 8))

        self.detail_panel = DocumentDetailPanel(right_wrap, controller=None)
        self.detail_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=(0, 8))

        # BOTTOM
        bottom = tk.Frame(self, highlightthickness=0, highlightbackground="#999")
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)

        self.bottom_bar = BottomBar(bottom, controller=None)
        self.bottom_bar.grid(row=0, column=0, sticky="ew", padx=12, pady=(0, 10))

        # ------------------------------------------------------------------
        # Compose repositories + services
        # ------------------------------------------------------------------
        self._repo_docs = DocumentRepositorySQLite()
        self._repo_roles = RoleRepositorySQLite()
        self._svc_docs = DocumentService(repo=self._repo_docs, roles=self._repo_roles)
        self._svc_ui_state = UIStateService(docs=self._repo_docs, roles=self._repo_roles)
        self._svc_creation = DocumentCreationService()

        # Current user provider
        if AppContextUserProvider is not None:  # type: ignore[truthy-bool]
            self._users = AppContextUserProvider()  # type: ignore[call-arg]
        else:
            self._users = DefaultCurrentUserProvider()

        # ------------------------------------------------------------------
        # Controllers (ONLY 4 controllers in this module)
        # ------------------------------------------------------------------
        self.bottom_bar_controller = BottomBarController(facade=self, user_provider=self._users)
        self.details_controller = DocumentDetailsController(
            view=self,
            doc_service=self._svc_docs,
            ui_state_service=self._svc_ui_state,
            user_provider=self._users,
        )
        self.list_controller = DocumentListController(
            view=self,
            doc_service=self._svc_docs,
            details_controller=self.details_controller,
            bottom_bar_controller=self.bottom_bar_controller,
        )
        self.topbar_controller = TopbarController(
            view=self,
            creation_service=self._svc_creation,
            user_provider=self._users,
        )

        # Wiring
        self._wire(self.list_panel, self.list_controller)
        self._wire(self.detail_panel, self.details_controller)  # panel doesn't use it yet, but ok
        self._wire(self.bottom_bar, self.bottom_bar_controller)
        self._wire(self.search_bar, self.topbar_controller)

        # Initial load
        try:
            self.list_controller.load_document_list()
        except Exception:
            pass

        self._apply_dev_borders()

    # helpers
    @staticmethod
    def _wire(component: Any, controller: Any) -> None:
        fn = getattr(component, "set_controller", None)
        if callable(fn):
            try:
                fn(controller)
                return
            except Exception:
                pass
        fn = getattr(component, "attach_controller", None)
        if callable(fn):
            try:
                fn(controller)
            except Exception:
                pass

    # surfaces
    def render_document_list(self, rows: list[dict]) -> None:
        try:
            self.list_panel.render_rows(rows)
        except Exception:
            pass

    def render_document_details(self, doc: Optional[dict]) -> None:
        """Render the right-hand detail panel.

        The detail panel API is `set_details(doc_id, details)`.
        For convenience, we accept either:
            - None (clears the panel)
            - a dict containing at least an 'id' key
        """
        try:
            if doc is None:
                self.detail_panel.set_details(-1, None)
                return
            doc_id = int(doc.get("id", -1)) if isinstance(doc, dict) else -1
            self.detail_panel.set_details(doc_id, doc)
        except Exception:
            pass

    def show_info(self, title: str, message: str) -> None:
        try:
            messagebox.showinfo(title=title, message=message, parent=self)
        except Exception:
            pass

    def show_error(self, title: str, message: str) -> None:
        try:
            messagebox.showerror(title=title, message=message, parent=self)
        except Exception:
            pass

    def show_warning(self, title: str, message: str) -> None:
        try:
            messagebox.showwarning(title=title, message=message, parent=self)
        except Exception:
            pass

    # search callback
    def _on_search_clicked(self, query: str) -> None:
        try:
            self.list_controller.action_search(query)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Facade API expected by BottomBarController
    # ------------------------------------------------------------------
    @property
    def view(self) -> Any:
        """Backwards compatible 'facade.view' surface expected by services."""
        return self

    def load_document_list(self) -> None:
        """Facade method used by action controllers to refresh the list."""
        self.list_controller.load_document_list()

    def on_select_document(self, doc_id: int) -> None:
        """Facade method used by action controllers to re-open details."""
        self.list_controller.on_select_document(doc_id)

    # dev-borders
    def _apply_dev_borders(self) -> None:
        enabled = bool(self._dev_borders_var.get())
        for child in self.winfo_children():
            try:
                if isinstance(child, tk.Frame):
                    child.configure(highlightthickness=1 if enabled else 0)
            except Exception:
                pass
        try:
            self._sm.set(self._FEATURE_ID, "ui_dev_borders", enabled)
        except Exception:
            pass
