"""documentlifecycle/controllers/document_list_controller.py

===============================================================================
DocumentListController – anemic list controller + selection forwarder
-------------------------------------------------------------------------------
Why this controller exists
    The left panel (Treeview) needs exactly ONE controller that offers:
        - load_document_list()
        - action_search(query)
        - on_select_document(doc_id)

    In the old setup a "facade controller" handled list+details together.
    This file replaces that façade by keeping responsibilities separated:
        - list loading/search -> DocumentService (read side)
        - selection -> forward to DocumentDetailsController
        - selection -> forward to BottomBarController (set_current_document)

SRP (strict)
    - No business logic, no repository calls in here.
    - This controller only calls services/controllers and tells the view to
      render the list.
===============================================================================
"""

from __future__ import annotations

from typing import Any, Dict, List


class DocumentListController:
    """UI-only controller for the document list area."""

    def __init__(
        self,
        *,
        view: Any,
        doc_service: Any,
        details_controller: Any | None = None,
        bottom_bar_controller: Any | None = None,
    ) -> None:
        self._view = view
        self._doc_svc = doc_service
        self._details_ctl = details_controller
        self._bottom_ctl = bottom_bar_controller

    # ------------------------------------------------------------------
    # List loading / search
    # ------------------------------------------------------------------
    def load_document_list(self) -> None:
        """Load the initial document list with default search settings."""
        rows: List[Dict[str, Any]] = self._doc_svc.search_documents(query=None)
        self._view.render_document_list(rows)

    def action_search(self, query: str) -> None:
        """Search and re-render the list."""
        rows: List[Dict[str, Any]] = self._doc_svc.search_documents(query=query or None)
        self._view.render_document_list(rows)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------
    def on_select_document(self, doc_id: int) -> None:
        """Forward list selection to the responsible controllers."""

        # 1) BottomBar must know which document actions apply to.
        if self._bottom_ctl is not None and hasattr(self._bottom_ctl, "set_current_document"):
            try:
                self._bottom_ctl.set_current_document(doc_id)
            except Exception:
                pass

        # 2) Details panel + UIState update.
        if self._details_ctl is not None and hasattr(self._details_ctl, "on_select_document"):
            try:
                self._details_ctl.on_select_document(doc_id)
            except Exception:
                pass
