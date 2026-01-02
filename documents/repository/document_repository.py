"""Document repository protocol (interface).

Defines the contract for document data access without implementation details.
"""

from __future__ import annotations
from typing import Protocol, List, Dict, Optional, Any
from datetime import datetime

from documents.models.document_models import DocumentRecord, DocumentStatus
from documents.dto.assignments import Assignments


class DocumentRepository(Protocol):
    """Protocol for document data access."""

    # ===== Query Operations =====

    def list(
            self,
            *,
            status: Optional[DocumentStatus] = None,
            text: Optional[str] = None,
            active_only: bool = False
    ) -> List[DocumentRecord]:
        """
        List documents with optional filters.

        Args:
            status: Filter by status
            text: Search in title/ID
            active_only: Only documents with active workflows

        Returns:
            List of DocumentRecord
        """
        ...

    def get(self, doc_id: str) -> Optional[DocumentRecord]:
        """
        Get single document by ID.

        Args:
            doc_id:  Document ID

        Returns:
            DocumentRecord or None
        """
        ...

    def exists(self, doc_id: str) -> bool:
        """Check if document exists."""
        ...

        # ===== Lifecycle Operations =====

    def create_from_file(
            self,
            *,
            title: Optional[str],
            doc_type: str,
            user_id: str,
            src_file: str
    ) -> DocumentRecord:
        """
        Create new document from file.

        Args:
            title: Document title (None = extract from filename)
            doc_type: Document type
            user_id: Creating user
            src_file: Source DOCX file path

        Returns:
            Created DocumentRecord
        """
        ...

    def update_metadata(
            self,
            data: Dict[str, Any],
            user_id: str
    ) -> None:
        """
        Update document metadata.

        Args:
            data: Metadata dict (must include 'doc_id')
            user_id: Updating user
        """
        ...

    def set_status(
            self,
            doc_id: str,
            status: DocumentStatus,
            user_id: str,
            reason: Optional[str] = None
    ) -> None:
        """
        Change document status.

        Args:
            doc_id: Document ID
            status: New status
            user_id: User making the change
            reason:  Reason for status change
        """
        ...

        # ===== Version Management =====

    def bump_minor_version(
            self,
            doc_id: str,
            user_id: str,
            reason: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Increment minor version (e.g., 1.0 → 1.1).

        Returns:
            (success, error_message)
        """
        ...

    def bump_major_version(
            self,
            doc_id: str,
            user_id: str,
            reason: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Increment major version (e.g., 1.5 → 2.0).

        Returns:
            (success, error_message)
        """
        ...

    # ===== Workflow State =====

    def is_workflow_active(self, doc_id: str) -> bool:
        """Check if workflow is active for document."""
        ...

    def set_workflow_active(
            self,
            doc_id: str,
            active: bool,
            started_by: Optional[str] = None
    ) -> None:
        """Set workflow active state."""
        ...

    def get_workflow_starter(self, doc_id: str) -> Optional[str]:
        """Get user ID who started the workflow."""
        ...

    # ===== Assignments =====

    def get_assignees(self, doc_id: str) -> Dict[str, List[str]]:
        """
        Get role assignments.

        Returns:
            Dict with keys: "AUTHOR", "REVIEWER", "APPROVER"
        """
        ...

    def set_assignees(
            self,
            doc_id: str,
            mapping: Dict[str, List[str]]
    ) -> None:
        """
        Set role assignments.

        Args:
            doc_id: Document ID
            mapping: Dict with keys "AUTHOR", "REVIEWER", "APPROVER"
        """
        ...

    def get_owner(self, doc_id: str) -> Optional[str]:
        """Get document owner user ID."""
        ...

    # ===== PDF Operations =====

    def generate_review_pdf(self, doc_id: str) -> Optional[str]:
        """
        Generate PDF for review (without markup).

        Returns:
            Path to generated PDF or None
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
            reason: Signature reason

        Returns:
            (success, error_message)
        """
        ...

    def export_pdf_with_version_suffix(self, doc_id: str) -> Optional[str]:
        """
        Export PDF with version number in filename.

        Returns:
            Path to exported PDF or None
        """
        ...

    def copy_to_destination(
            self,
            doc_id: str,
            dest_dir: str
    ) -> Optional[str]:
        """
        Copy controlled document to destination (with watermark).

        Returns:
            Path to copied file or None
        """
        ...

        # ===== Comments =====

    def list_comments(self, doc_id: str) -> List[Dict[str, Any]]:
        """
        Get all comments for document.

        Returns:
            List of comment dicts with keys: author, date, text
        """
        ...

    def get_docx_comments_for_version(
            self,
            doc_id: str,
            version_label: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get DOCX comments for specific version.

        Args:
            doc_id: Document ID
            version_label: Version (e.g., "1.0"), None = current

        Returns:
            List of comment dicts
        """
        ...

    # ===== File Management =====

    def check_in(
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