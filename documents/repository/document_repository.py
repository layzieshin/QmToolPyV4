"""Document repository protocol (interface).

Defines the contract for document data access without implementation details.
"""

from __future__ import annotations
from typing import Protocol, List, Dict, Optional, Any
from datetime import datetime
from core.qm_logging.logic.logger import logger
from documents.models.document_models import DocumentRecord, DocumentStatus
from documents.dto.assignments import Assignments


class DocumentRepository(Protocol):
    """Protocol for document data access."""

    def create(self, record: DocumentRecord) -> None:
        """Create a new document record."""
        ...

    def get(self, doc_id: str) -> Optional[DocumentRecord]:
        """Get document by ID."""
        ...

    def update(self, doc_id: str, updates: Dict[str, Any]) -> bool:
        """Update document fields."""
        ...

    def delete(self, doc_id: str) -> bool:
        """Delete document record."""
        ...

    def list(self) -> List[DocumentRecord]:
        """List all documents."""
        ...

    def search(self, query: str) -> List[DocumentRecord]:
        """Search documents by query."""
        ...

    def set_status(self, doc_id: str, status: DocumentStatus, user_id: str, reason: str) -> bool:
        """Set document status."""
        ...

    def bump_minor_version(self, doc_id: str, user_id: str, reason: str) -> bool:
        """Increment minor version."""
        ...

    def get_owner(self, doc_id: str) -> Optional[str]:
        """Get document owner user ID."""
        ...

    # ===== Workflow State =====

    def is_workflow_active(self, doc_id: str) -> bool:
        """Return True if workflow is active for this document."""
        ...

    def set_workflow_active(self, doc_id: str, active: bool, started_by: Optional[str] = None) -> None:
        """Set workflow active state."""
        ...

    def get_workflow_starter(self, doc_id: str) -> Optional[str]:
        """Return the user ID of the workflow starter, if known."""
        ...

    # ===== Assignments =====

    def get_assignments(self, doc_id: str) -> Assignments:
        """Get current role assignments for document."""
        ...

    def set_assignments(self, doc_id: str, assignments: Assignments) -> None:
        """Replace role assignments for document."""
        ...

    
    # ===== Signatures =====

    def list_signatures(self, doc_id: str) -> List[Dict[str, Any]]:
        """Return signature rows for the given document."""
        if not doc_id:
            return []
        try:
            rows = self._db.fetchall(
                "SELECT doc_id, role, username, signed_at, comment "
                "FROM signatures WHERE doc_id = ? ORDER BY signed_at ASC",
                (doc_id,),
            )
            return [dict(r) for r in (rows or [])]
        except Exception as ex:
            logger.error(f"Error listing signatures for {doc_id}: {ex}")
            return []


# ===== PDF Operations =====

    def generate_review_pdf(self, doc_id: str) -> Optional[str]:
        """
        Generate PDF for review (without markup).

        Returns:
            Path to generated PDF or None
        """
        ...

    def get_signing_pdf(self, doc_id: str) -> Optional[str]:
        """
        Return the current signing PDF path for the document, if any.

        This is the single active PDF that is passed along the signing chain.
        """
        ...

    def set_signing_pdf(self, doc_id: str, pdf_path: str) -> None:
        """
        Persist the current signing PDF path for the document.

        The path MUST always reference the latest signed PDF (single active artifact).
        """
        ...

    def clear_signing_pdf(self, doc_id: str) -> None:
        """
        Clear signing PDF reference for the document (e.g. on workflow abort).
        """
        ...

    def attach_signed_pdf(
        self,
        doc_id: str,
        signed_pdf_path: str,
        step: str,
        user_id: str,
        reason: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Attach signed PDF to document.

        Args:
            doc_id: Document ID
            signed_pdf_path: Path to signed PDF
            step:  Workflow step (e.g., "submit_review", "approve", "publish")
            user_id: User who signed
            reason: Optional reason/comment

        Returns:
            (success, message)
        """
        ...

    def export_pdf_with_version_suffix(self, doc_id: str) -> Optional[str]:
        """Export PDF with version number in filename."""
        ...

    def copy_to_destination(self, doc_id: str, dest_dir: str) -> Optional[str]:
        """Copy controlled document to destination directory."""
        ...

    # ===== File Operations =====

    def checkout(
        self,
        doc_id: str,
        user_id: str,
        *,
        comment: Optional[str] = None
    ) -> Optional[str]:
        """
        Checkout document for editing.

        Returns:
            Path to checked-out file or None
        """
        ...

    def checkin(
        self,
        doc_id: str,
        user_id: str,
        file_path: str,
        comment: Optional[str] = None
    ) -> None:
        """
        Check in new file version.

        Args:
            doc_id: Document ID
            user_id: User checking in
            file_path: Path to new file
            comment: Check-in comment
        """
        ...
