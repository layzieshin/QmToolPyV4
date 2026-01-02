"""DocumentCreationController - handles document creation and metadata updates."""

from __future__ import annotations
from typing import Any, Callable, Dict, Optional, Tuple
import os

from documents.models.document_models import DocumentRecord

class DocumentCreationController:
    """
    Handles document creation and metadata updates.

    Responsibilities:
    - Create from template
    - Import file
    - Update metadata

    SRP: Document lifecycle start, no workflow logic.
    """

    def __init__(
            self,
            *,
            repository: DocumentsRepository,
            current_user_provider: Callable[[], Optional[object]]
    ) -> None:
        """
        Args:
            repository: Documents repository
            current_user_provider:  Lambda that returns current user
        """
        self._repo = repository
        self._user_provider = current_user_provider

    def create_from_template(
            self,
            template_path: str,
            doc_type: str = "SOP"
    ) -> Tuple[bool, Optional[str], Optional[DocumentRecord]]:
        """
        Create document from template.

        Args:
            template_path: Path to DOCX template
            doc_type: Document type

        Returns:
            (success:  bool, error_msg: Optional[str], record: Optional[DocumentRecord])
        """
        if not os.path.isfile(template_path):
            return False, f"Template nicht gefunden: {template_path}", None

        try:
            user_id = self._get_user_id()
            record = self._repo.create_from_file(
                title=None,  # Will be extracted from filename
                doc_type=doc_type,
                user_id=user_id,
                src_file=template_path
            )
            return True, None, record
        except Exception as ex:
            return False, f"Fehler beim Erstellen:  {ex}", None

    def import_file(
            self,
            file_path: str,
            doc_type: str = "SOP"
    ) -> Tuple[bool, Optional[str], Optional[DocumentRecord]]:
        """
        Import existing DOCX file.

        Args:
            file_path:  Path to DOCX
            doc_type: Document type

        Returns:
            (success: bool, error_msg:  Optional[str], record: Optional[DocumentRecord])
        """
        if not os.path.isfile(file_path):
            return False, f"Datei nicht gefunden: {file_path}", None

        if not file_path.lower().endswith(".docx"):
            return False, "Nur DOCX-Dateien werden unterstützt.", None

        try:
            user_id = self._get_user_id()
            record = self._repo.create_from_file(
                title=None,
                doc_type=doc_type,
                user_id=user_id,
                src_file=file_path
            )
            return True, None, record
        except Exception as ex:
            return False, f"Import fehlgeschlagen: {ex}", None

    def update_metadata(
            self,
            doc_id: str,
            metadata: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Update document metadata.

        Args:
            doc_id: Document ID
            metadata: Metadata dict (title, doc_type, area, process, next_review)

        Returns:
            (success: bool, error_msg: Optional[str])
        """
        try:
            user_id = self._get_user_id()
            data = {"doc_id": doc_id, **metadata}
            self._repo.update_metadata(data, user_id)
            return True, None
        except Exception as ex:
            return False, f"Metadaten-Update fehlgeschlagen: {ex}"

    def _get_user_id(self) -> Optional[str]:
        """Get current user ID."""
        user = self._user_provider()
        if not user:
            return None

        for attr in ("id", "user_id", "uid"):
            val = getattr(user, attr, None)
            if val:
                return str(val)
        return None