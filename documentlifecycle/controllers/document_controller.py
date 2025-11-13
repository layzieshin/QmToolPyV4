"""
===============================================================================
DocumentLifecycleController – list & detail orchestration (service-backed)
-------------------------------------------------------------------------------
Purpose
    - Load and render the document list from the repository via DocumentService.
    - On selection: fetch details and inform the WorkflowController so that
      BottomBar actions operate on the correct document.
    - Provide a tiny search action that reuses the same list loader.

Design (SRP)
    - No business rules here, no file/DB logic. Pure UI orchestration.
    - Repository access goes through DocumentService (DTO/Dict for the view).
    - Resilient imports: tries concrete SQLite repositories; falls back to
      'fake_data' when unavailable so the UI keeps working.

Conventions
    - All UI texts are looked up via T("documentlifecycle.*") where applicable.
===============================================================================
"""
from __future__ import annotations

from typing import Optional, Any

# i18n
try:
    from core.common.app_context import T  # type: ignore
except Exception:  # pragma: no cover
    def T(_key: str) -> str:  # fallback
        return ""

# --- Repositories (robust import tries) -------------------------------------
_repo_impl = None
_roles_impl = None

# Try typical SQLite paths first
try:
    from documentlifecycle.logic.repository.sqlite.document_repository_sqlite import (  # type: ignore
        DocumentRepositorySQLite as _RepoImpl,
    )
    _repo_impl = _RepoImpl()
except Exception:
    try:
        # alternative layout
        from documentlifecycle.logic.repository.document_repository_sqlite import (  # type: ignore
            DocumentRepositorySQLite as _RepoImpl,
        )
        _repo_impl = _RepoImpl()
    except Exception:
        _repo_impl = None

try:
    from documentlifecycle.logic.repository.sqlite.role_repository_sqlite import (  # type: ignore
        RoleRepositorySQLite as _RolesImpl,
    )
    _roles_impl = _RolesImpl()
except Exception:
    try:
        from documentlifecycle.logic.repository.role_repository_sqlite import (  # type: ignore
            RoleRepositorySQLite as _RolesImpl,
        )
        _roles_impl = _RolesImpl()
    except Exception:
        _roles_impl = None

# Fallback data so the UI stays alive if repos are missing
try:
    from documentlifecycle.logic import fake_data as _fake  # type: ignore
except Exception:  # pragma: no cover
    class _fake:  # minimal stub
        @staticmethod
        def fake_list() -> list[dict]:
            return []
        @staticmethod
        def fake_detail(doc_id: int) -> dict:
            return {"id": doc_id, "title": f"Document #{doc_id}", "status": "-", "updated": ""}

# Service (your uploaded implementation with search_documents/get_details)
from documentlifecycle.logic.services.document_service import DocumentService  # type: ignore


class DocumentLifecycleController:
    """
    UI Controller for the Document Lifecycle main view (list + details).
    BottomBar actions are handled by a separate WorkflowController.
    """

    def __init__(self, view) -> None:
        self._view = view
        self._current_doc_id: Optional[int] = None
        self._workflow: Optional[Any] = None

        # Instantiate the read service when repositories are available.
        # If repos are missing, we fall back to fake data.
        if _repo_impl and _roles_impl:
            self._svc = DocumentService(repo=_repo_impl, roles=_roles_impl)
        else:
            self._svc = None

    # -------- wiring ---------------------------------------------------------
    def set_workflow_controller(self, workflow_controller: Any) -> None:
        """Inject WorkflowController so BottomBar actions receive the selection."""
        self._workflow = workflow_controller

    # -------- list & details -------------------------------------------------
    def load_document_list(self, query: Optional[str] = None) -> None:
        """
        Load list rows for the left panel.
        Uses DocumentService.search_documents(...) when available,
        otherwise falls back to fake_data.
        """
        if self._svc:
            try:
                rows = self._svc.search_documents(query=query)
            except Exception:
                rows = []
        else:
            rows = _fake.fake_list()
        self._view.render_document_list(rows)

    def on_select_document(self, doc_id: int) -> None:
        """
        Load details for the right panel and inform WorkflowController
        about the current selection (so BottomBar acts on the right doc).
        """
        self._current_doc_id = doc_id

        if self._svc:
            try:
                details = self._svc.get_details(doc_id) or {}
            except Exception:
                details = {}
        else:
            details = _fake.fake_detail(doc_id)

        self._view.render_document_details(details)

        if self._workflow and hasattr(self._workflow, "set_current_document"):
            try:
                self._workflow.set_current_document(doc_id)
            except Exception:
                pass

    # -------- search bar action ---------------------------------------------
    def action_search(self, query: str) -> None:
        """Simple search that reuses the same list loader with a query."""
        self.load_document_list(query=query)
