"""DocumentDetailsController - computes document details and UI state.

REFACTORED: Uses UIStateService instead of direct workflow/permission checks.
"""

from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional
import os

from documents.models.document_models import DocumentRecord, DocumentStatus
from documents.repository.document_repository import DocumentRepository
from documents.services.ui_state_service import UIStateService
from documents.dto.document_details import DocumentDetails
from documents.dto.controls_state import ControlsState

# Word metadata bridge (optional)
try:
    from documents.logic.wordmeta_bridge import extract_core_and_comments
except Exception:
    def extract_core_and_comments(path: str):
        return {}, []


class DocumentDetailsController:
    """
    Computes document details and UI state.

    REFACTORED:
    - Uses UIStateService for button state computation
    - Separates concerns (no direct policy checks)
    """

    def __init__(
        self,
        *,
        repository: DocumentRepository,
        ui_state_service: UIStateService,
        current_user_provider: Callable[[], Optional[object]]
    ) -> None:
        """
        Args:
            repository: Documents repository
            ui_state_service: UI state computation service
            current_user_provider: Lambda that returns current user
        """
        self._repo = repository
        self._ui_state = ui_state_service
        self._user_provider = current_user_provider

    def get_details(self, doc_id: str) -> Optional[DocumentDetails]:
        """
        Load complete details including metadata and comments.

        Args:
            doc_id: Document ID

        Returns:
            DocumentDetails DTO or None if not found
        """
        record = self._repo.get(doc_id)
        if not record:
            return None

        # Get metadata from DOCX
        core_meta = self._get_docx_meta(record)

        # Get current actors (effective for current workflow step)
        actors = self._get_actual_actors(record)

        # Get comments
        docx_comments = self.get_comments(doc_id)

        # Determine actual file type
        path = record.current_file_path or ""
        actual_ftype = os.path.splitext(path)[1][1:].upper() if path else ""

        return DocumentDetails(
            doc_id=record.doc_id.value,
            title=record.title,
            doc_type=record.doc_type,
            status=record.status.name if hasattr(record.status, "name") else str(record.status),
            version_label=f"{record.version_major}.{record.version_minor}",
            current_file_path=record.current_file_path,

            # Metadata
            description=core_meta.get("description"),
            documenttype=core_meta.get("documenttype") or record.doc_type,
            actual_filetype=actual_ftype or core_meta.get("actual_filetype"),
            valid_by_date=core_meta.get("valid_by_date"),
            last_modified=core_meta.get("last_modified"),

            # Actors
            editor=actors.get("editor"),
            reviewer=actors.get("reviewer"),
            publisher=actors.get("publisher"),
            editor_dt=actors.get("editor_dt"),
            reviewer_dt=actors.get("reviewer_dt"),
            publisher_dt=actors.get("publisher_dt"),

            # Comments
            docx_comments=docx_comments,
            pdf_comments=[],  # TODO: PDF comments if needed
        )

    def compute_controls_state(
        self,
        record: DocumentRecord,
        *,
        user_roles: List[str],
        assigned_roles: List[str]
    ) -> ControlsState:
        """
        Compute UI state (button enablement and text).

        Args:
            record: Document record
            user_roles: User's system roles (e.g., ["ADMIN"], ["USER"])
            assigned_roles: User's assigned roles on this doc (e.g., ["REVIEWER"])

        Returns:
            ControlsState DTO
        """
        user = self._user_provider()
        if not user:
            return ControlsState.disabled()

        # Get context
        workflow_active = self._repo.is_workflow_active(record.doc_id.value)
        workflow_starter_id = self._repo.get_workflow_starter(record.doc_id.value)
        owner_id = self._repo.get_owner(record.doc_id.value)
        user_id = self._get_user_id(user)

        # Can open file?
        can_open_file = bool(
            record.current_file_path and
            os.path.isfile(record.current_file_path or "")
        )

        # Delegate to UIStateService
        return self._ui_state.build_controls_state(
            status=record.status,
            doc_type=record.doc_type,
            user_roles=user_roles,
            assigned_roles=assigned_roles,
            workflow_active=workflow_active,
            can_open_file=can_open_file,
            user_id=user_id,
            owner_id=owner_id,
            workflow_starter_id=workflow_starter_id
        )

    def get_comments(self, doc_id: str) -> List[Dict[str, Any]]:
        """
        Load comments only (for separate refresh).

        Args:
            doc_id: Document ID

        Returns:
            List of comment dicts
        """
        return self._repo.list_comments(doc_id)

    # ----------------------------------------------------------------- Helpers

    def _get_docx_meta(self, record: DocumentRecord) -> Dict[str, Any]:
        """Extract DOCX core properties."""
        path = record.current_file_path
        if not path or not os.path.isfile(path):
            return {}

        try:
            core, _ = extract_core_and_comments(path)
            return core
        except Exception:
            return {}

    def _get_actual_actors(self, record:  DocumentRecord) -> Dict[str, Optional[str]]:
        """Get current actors (effective for current workflow step)."""
        # TODO: Implement actual actor resolution based on workflow state
        # For now, return empty
        return {
            "editor": None,
            "reviewer": None,
            "publisher": None,
            "editor_dt": None,
            "reviewer_dt": None,
            "publisher_dt": None,
        }

    def _get_user_id(self, user: object) -> Optional[str]:
        """Extract user ID from user object."""
        for attr in ("id", "user_id", "uid"):
            val = getattr(user, attr, None)
            if val:
                return str(val)
        return None