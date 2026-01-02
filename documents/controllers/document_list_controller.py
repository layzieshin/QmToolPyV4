"""DocumentListController - manages document list loading."""

from __future__ import annotations
from typing import List, Optional

from documents.models.document_models import DocumentRecord, DocumentStatus
from documents.controllers.search_filter_controller import SearchFilterController


class DocumentListController:
    """
    Manages document list loading and caching.

    Responsibilities:
    - Load documents with filters
    - Get single document
    - Refresh list

    Delegates to SearchFilterController for filtering/sorting.
    """

    def __init__(
            self,
            *,
            repository: DocumentsRepository,
            filter_controller: SearchFilterController
    ) -> None:
        """
        Args:
            repository: Documents repository
            filter_controller: Filter/search logic
        """
        self._repo = repository
        self._filter_ctrl = filter_controller

    def load_documents(
            self,
            *,
            text: Optional[str] = None,
            status: Optional[DocumentStatus] = None,
            active_only: bool = False,
            sort_mode: str = "updated"
    ) -> List[DocumentRecord]:
        """
        Load and filter documents.

        Args:
            text: Search text
            status: Status filter
            active_only: Only active workflows
            sort_mode: Sort mode

        Returns:
            List of DocumentRecord
        """
        # Apply filters
        documents = self._filter_ctrl.apply_filters(
            text=text,
            status=status,
            active_only=active_only
        )

        # Sort
        return self._filter_ctrl.sort_documents(documents, sort_mode)

    def get_document(self, doc_id: str) -> Optional[DocumentRecord]:
        """
        Get single document by ID.

        Args:
            doc_id:  Document ID

        Returns: 
            DocumentRecord or None
        """
        return self._repo.get(doc_id)

    def refresh(self, sort_mode: str = "updated") -> List[DocumentRecord]:
        """
        Refresh list with last filter settings.

        Args:
            sort_mode: Sort mode

        Returns:
            Current document list
        """
        documents = self._filter_ctrl.refresh()
        return self._filter_ctrl.sort_documents(documents, sort_mode)