"""
===============================================================================
Bottom Bar (Document Lifecycle) – UI with document/workflow actions
-------------------------------------------------------------------------------
Purpose
    - Left block: Read, Print, Edit, Finish & Sign, Archive, Edit Roles.
    - Right block (spaced): Start Workflow / Cancel Workflow.

Notes
    - Pure View (Tkinter/ttk). No business logic.
    - All label keys use the "documentlifecycle." prefix.
    - API for controllers/facade:
        set_controller(obj), set_sign_visible(bool), set_archive_visible(bool),
        set_edit_roles_visible(bool), set_print_enabled(bool),
        show_workflow_start(), show_workflow_cancel(), show_workflow_abort() [alias]
===============================================================================
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Optional

try:
    from core.common.app_context import T  # type: ignore
except Exception:  # pragma: no cover
    def T(key: str) -> str: return ""


class BottomBar(ttk.Frame):
    def __init__(self, master: tk.Misc, **kwargs) -> None:
        kwargs.pop("search", None)  # swallow legacy unknown option
        super().__init__(master, **kwargs)
        self._controller: Optional[object] = None

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)

        left = ttk.Frame(self)
        right = ttk.Frame(self)
        left.grid(row=0, column=0, sticky="w", padx=8, pady=6)
        right.grid(row=0, column=1, sticky="e", padx=8, pady=6)

        # Left group
        ttk.Button(
            left, text=(T("documentlifecycle.document.read") or "Lesen"),
            command=lambda: self._call_ctrl("action_open_read")
        ).grid(row=0, column=0, padx=6)

        self._btn_print = ttk.Button(
            left, text=(T("documentlifecycle.document.print") or "Drucken"),
            command=lambda: self._call_ctrl("action_print")
        )
        self._btn_print.grid(row=0, column=1, padx=6)

        ttk.Button(
            left, text=(T("documentlifecycle.document.edit") or "Bearbeiten"),
            command=lambda: self._call_ctrl("action_edit")
        ).grid(row=0, column=2, padx=6)

        self._btn_sign = ttk.Button(
            left, text=(T("documentlifecycle.document.sign") or "Fertig & Signieren"),
            command=lambda: self._call_ctrl("action_finish_and_sign")
        )
        self._btn_sign.grid(row=0, column=3, padx=6)

        self._btn_archive = ttk.Button(
            left, text=(T("documentlifecycle.document.archive") or "Archivieren"),
            command=lambda: self._call_ctrl("action_archive")
        )
        self._btn_archive.grid(row=0, column=4, padx=6)

        self._btn_roles = ttk.Button(
            left, text=(T("documentlifecycle.document.roles.edit") or "Rollen bearbeiten"),
            command=lambda: self._call_ctrl("action_edit_roles")
        )
        self._btn_roles.grid(row=0, column=5, padx=6)

        # Hide privileged by default – controller/state will reveal
        self._grid_remove_safe(self._btn_sign)
        self._grid_remove_safe(self._btn_archive)
        self._grid_remove_safe(self._btn_roles)

        # Right group (workflow)
        self._btn_wf_start = tk.Button(
            right, text=(T("documentlifecycle.workflow.start") or "Workflow starten"),
            command=lambda: self._call_ctrl("action_workflow_start"),
            bg="#dcfacb", activebackground="#dcfacb"
        ); self._btn_wf_start.grid(row=0, column=0, padx=(12, 6))

        self._btn_wf_cancel = tk.Button(
            right, text=(T("documentlifecycle.workflow.cancel") or "Workflow abbrechen"),
            command=lambda: self._call_ctrl("action_workflow_cancel"),
            bg="#facbcf", activebackground="#facbcf"
        ); self._btn_wf_cancel.grid(row=0, column=1, padx=(6, 12))

        self._grid_remove_safe(self._btn_wf_cancel)  # default: only START visible

    # ---- controller wiring ---- #
    def set_controller(self, controller: object) -> None:
        self._controller = controller

    # legacy aliases
    def attachController(self, controller: object) -> None:  # noqa: N802
        self.set_controller(controller)
    def attach_controller(self, controller: object) -> None:
        self.set_controller(controller)
    def attachcontroller(self, controller: object) -> None:
        self.set_controller(controller)

    # ---- visibility/enable toggles ---- #
    def set_sign_visible(self, flag: bool) -> None:
        (self._grid_add_safe if flag else self._grid_remove_safe)(self._btn_sign)

    def set_archive_visible(self, flag: bool) -> None:
        (self._grid_add_safe if flag else self._grid_remove_safe)(self._btn_archive)

    def set_edit_roles_visible(self, flag: bool) -> None:
        (self._grid_add_safe if flag else self._grid_remove_safe)(self._btn_roles)

    def set_print_enabled(self, flag: bool) -> None:
        try:
            state = "normal" if flag else "disabled"
            self._btn_print.configure(state=state)
        except Exception:
            pass

    def show_workflow_start(self) -> None:
        self._grid_add_safe(self._btn_wf_start); self._grid_remove_safe(self._btn_wf_cancel)

    def show_workflow_cancel(self) -> None:
        self._grid_add_safe(self._btn_wf_cancel); self._grid_remove_safe(self._btn_wf_start)

    # alias (older code)
    def show_workflow_abort(self) -> None:  # pragma: no cover
        self.show_workflow_cancel()

    # ---- internals ---- #
    def _call_ctrl(self, method_name: str) -> None:
        ctl = self._controller
        if not ctl:
            return
        fn = getattr(ctl, method_name, None)
        if callable(fn):
            try:
                fn()
            except Exception:
                pass

    @staticmethod
    def _grid_remove_safe(w: tk.Widget) -> None:
        try: w.grid_remove()
        except Exception: pass

    @staticmethod
    def _grid_add_safe(w: tk.Widget) -> None:
        try: w.grid()
        except Exception: pass


class DocumentLifecycleBottomBar(BottomBar):
    """Backwards-compatible alias."""
    pass
