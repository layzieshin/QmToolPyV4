"""documentlifecycle/controllers/document_details_controller.py

===============================================================================
DocumentDetailsController – anemic details renderer + UI state application
-------------------------------------------------------------------------------
Purpose
    - On list selection: load details via DocumentService and render them.
    - Compute the BottomBar visibility state via UIStateService and apply it.

Strict SRP
    - No database access.
    - No workflow transitions.
    - No dialog code.
    - Only reads via services and updates the view.

Important note about workflow_starter_id
    The UIStateService API supports an optional workflow_starter_id for the
    abort policy. The current project does not persist / expose that starter id
    yet, so this controller always passes None.
===============================================================================
"""

from __future__ import annotations

from typing import Any


class DocumentDetailsController:
    """UI-only controller for the detail panel (and BottomBar state)."""

    def __init__(self, *, view: Any, doc_service: Any, ui_state_service: Any, user_provider: Any) -> None:
        self._view = view
        self._doc_svc = doc_service
        self._ui_svc = ui_state_service
        self._user_provider = user_provider

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def on_select_document(self, doc_id: int) -> None:
        """Load + render details and update BottomBar visibility."""

        # 1) Details
        details = None
        try:
            details = self._doc_svc.get_details(doc_id)
        except Exception:
            details = None

        # Preferred surface: consolidated view method
        try:
            render = getattr(self._view, "render_document_details", None)
            if callable(render):
                render(details)
            else:
                # Fallback: legacy detail_panel.set_details
                panel = getattr(self._view, "detail_panel", None)
                setter = getattr(panel, "set_details", None)
                if callable(setter):
                    setter(doc_id, details or {})
        except Exception:
            pass

        # 2) UI state
        try:
            user = self._user_provider.get_current_user()
        except Exception:
            user = None

        try:
            state = self._ui_svc.compute(doc_id=doc_id, user=user, workflow_starter_id=None)
            self._apply_ui_state(state)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _apply_ui_state(self, state: Any) -> None:
        """Apply visibility flags from UIState to BottomBar (defensive)."""
        bb = getattr(self._view, "bottom_bar", None)
        if not bb:
            return

        # Workflow buttons
        try:
            if getattr(state, "show_workflow_start", False) and hasattr(bb, "show_workflow_start"):
                bb.show_workflow_start()

            show_abort = getattr(state, "show_workflow_abort", False) or getattr(state, "show_workflow_cancel", False)
            if show_abort:
                if hasattr(bb, "show_workflow_cancel"):
                    bb.show_workflow_cancel()
                elif hasattr(bb, "show_workflow_abort"):
                    bb.show_workflow_abort()
        except Exception:
            pass

        # Privileged buttons
        for meth_name, flag in (
            ("set_sign_visible", getattr(state, "show_sign", False)),
            ("set_archive_visible", getattr(state, "show_archive", False)),
            ("set_edit_roles_visible", getattr(state, "show_edit_roles", False)),
        ):
            fn = getattr(bb, meth_name, None)
            if callable(fn):
                try:
                    fn(bool(flag))
                except Exception:
                    pass
