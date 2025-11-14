"""
===============================================================================
DocumentLifecycleView – 3-Zonen-Layout (Search | List+Details | Bottom)
-------------------------------------------------------------------------------
Role
    - Compose GUI: SearchBar (top), DocumentListPanel (left), DocumentDetailPanel (right),
      BottomBar (bottom).
    - Wire controllers:
        * DocumentLifecycleController -> list + details
        * WorkflowController         -> bottom bar actions
        * CreationController         -> search bar (Import/Neu aus Vorlage)
      and forward selection to WorkflowController (set_current_document).
    - Provide simple info/error surfaces for controllers.
Design
    - Pure UI composition (SRP). No business logic.
    - Robust wiring: supports both set_controller(...) and attach_controller(...).
    - Dev-borders toggle persisted via SettingsManager.
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

# Controllers
from documentlifecycle.controllers.document_controller import DocumentLifecycleController
from documentlifecycle.controllers.workflow_controller import WorkflowController
from documentlifecycle.controllers.creation_controller import CreationController

# Services (für CreationController)
from documentlifecycle.logic.services.document_creation_service import DocumentCreationService


class DocumentLifecycleView(ttk.Frame):
    """
    Main composition frame for the Document Lifecycle feature.
    """

    _FEATURE_ID = "documentlifecycle"  # for storing UI dev-border preference

    def __init__(self, parent: tk.Widget, *,
                 settings_manager: Optional[SettingsManager] = None,
                 sm: Optional[SettingsManager] = None,
                 **_ignore) -> None:
        super().__init__(parent)

        # ------------------------------------------------------------------ #
        # Settings / layout grid
        # ------------------------------------------------------------------ #
        self._sm: SettingsManager = (settings_manager or sm) or SettingsManager()  # type: ignore
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)  # middle grows

        self._dev_borders_var = tk.BooleanVar(
            value=bool(self._sm.get(self._FEATURE_ID, "ui_dev_borders", False))
        )

        # ------------------------------------------------------------------ #
        # TOP: header + search bar
        # ------------------------------------------------------------------ #
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

        # ------------------------------------------------------------------ #
        # MIDDLE: split left/right
        # ------------------------------------------------------------------ #
        mid = tk.Frame(self, highlightthickness=0, highlightbackground="#999")
        mid.grid(row=1, column=0, sticky="nsew")
        mid.columnconfigure(0, weight=1)
        mid.columnconfigure(1, weight=2)
        mid.rowconfigure(0, weight=1)

        left_wrap = tk.Frame(mid, highlightthickness=0, highlightbackground="#999")
        left_wrap.grid(row=0, column=0, sticky="nsew")
        right_wrap = tk.Frame(mid, highlightthickness=0, highlightbackground="#999")
        right_wrap.grid(row=0, column=1, sticky="nsew")

        self.list_panel = DocumentListPanel(left_wrap, controller=None)
        self.list_panel.grid(row=0, column=0, sticky="nsew", padx=12, pady=(0, 8))

        self.detail_panel = DocumentDetailPanel(right_wrap, controller=None)
        self.detail_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=(0, 8))

        # ------------------------------------------------------------------ #
        # BOTTOM: bottom bar
        # ------------------------------------------------------------------ #
        bottom = tk.Frame(self, highlightthickness=0, highlightbackground="#999")
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)

        self.bottom_bar = BottomBar(bottom, controller=None)
        self.bottom_bar.grid(row=0, column=0, sticky="ew", padx=12, pady=(0, 10))

        # ------------------------------------------------------------------ #
        # Instantiate + wire controllers
        # ------------------------------------------------------------------ #
        self.controller = DocumentLifecycleController(view=self)
        self.workflow_controller = WorkflowController(facade=self, ui_service=None, user_provider=None)

        # 👉 NEU: CreationController + Service
        self.creation_controller = CreationController(
            view=self,
            creation_service=DocumentCreationService(),
            user_provider=None,  # AppContext-Provider nutzt der Controller intern automatisch, wenn vorhanden
        )

        # list + details -> DocumentLifecycleController
        self._wire_controller(self.list_panel, self.controller)
        self._wire_controller(self.detail_panel, self.controller)

        # bottom bar -> WorkflowController (Buttons erwarten action_* Methoden)
        self._wire_controller(self.bottom_bar, self.workflow_controller)

        # search bar -> CreationController (fixes: "kein Controller connected")
        self._wire_controller(self.search_bar, self.creation_controller)

        # let the list/detail controller inform workflow controller about selection
        if hasattr(self.controller, "set_workflow_controller"):
            try:
                self.controller.set_workflow_controller(self.workflow_controller)
            except Exception:
                pass

        # initial list load
        if hasattr(self.controller, "load_document_list"):
            try:
                self.controller.load_document_list()
            except Exception:
                pass

        # dev borders
        self._apply_dev_borders()

    # ---------------------------------------------------------------------- #
    # Helper: tolerant wiring (set_controller or attach_controller)
    # ---------------------------------------------------------------------- #
    @staticmethod
    def _wire_controller(component: Any, controller: Any) -> None:
        """
        Try set_controller(...) first, then fallback to attach_controller(...).
        Silent if neither exists.
        """
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

    # ---------------------------------------------------------------------- #
    # Controller hooks
    # ---------------------------------------------------------------------- #
    def render_document_list(self, rows: list[dict]) -> None:
        if hasattr(self.list_panel, "render_rows"):
            try:
                self.list_panel.render_rows(rows)
            except Exception:
                pass

    def render_document_details(self, doc: Optional[dict]) -> None:
        if hasattr(self.detail_panel, "render_details"):
            try:
                self.detail_panel.render_details(doc)
            except Exception:
                pass

    # Optional surfaces for controllers
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

    # ---------------------------------------------------------------------- #
    # Search callback
    # ---------------------------------------------------------------------- #
    def _on_search_clicked(self, query: str) -> None:
        if hasattr(self.controller, "action_search"):
            try:
                self.controller.action_search(query)
            except Exception:
                pass

    # ---------------------------------------------------------------------- #
    # Dev borders
    # ---------------------------------------------------------------------- #
    def _apply_dev_borders(self) -> None:
        enabled = bool(self._dev_borders_var.get())
        for wrap in self.winfo_children():
            try:
                if isinstance(wrap, tk.Frame):
                    wrap.configure(highlightthickness=1 if enabled else 0)
            except Exception:
                pass
        try:
            self._sm.set(self._FEATURE_ID, "ui_dev_borders", enabled)
        except Exception:
            pass
