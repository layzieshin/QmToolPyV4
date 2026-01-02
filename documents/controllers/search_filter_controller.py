"""SearchFilterController - handles search and filter logic."""

from __future__ import annotations
from typing import List, Optional

from documents.models.document_models import DocumentRecord, DocumentStatus
from documents.logic.repository import DocumentsRepository


class SearchFilterController:
    """
    Stateless controller for search and filter operations.

    Responsibilities:
    - Apply search/status/active filters
    - Sort document lists

    SRP: No UI, no workflow logic, only data filtering.
    """

    def __init__(self, *, repository: DocumentsRepository) -> None:
        """
        Args:
            repository: Documents repository for data access
        """
        self._repo = repository
        self._last_filters = {
            "text": None,
            "status": None,
            "active_only": False,
        }

    def apply_filters(
            self,
            *,
            text: Optional[str] = None,
            status: Optional[DocumentStatus] = None,
            active_only: bool = False
    ) -> List[DocumentRecord]:
        """
        Apply filters and return filtered list.

        Args:
            text: Search text (title/ID)
            status: Status filter
            active_only: Only active workflows

        Returns:
            List of DocumentRecord (sorted by updated_at DESC by default)
        """
        # Cache last filters for refresh
        self._last_filters["text"] = text
        self._last_filters["status"] = status
        self._last_filters["active_only"] = active_only

        # Delegate to repository
        return self._repo.list(
            status=status,
            text=text,
            active_only=active_only
        )

    def refresh(self) -> List[DocumentRecord]:
        """
        Refresh list with last applied filters.

        Returns:
            Filtered document list
        """
        return self.apply_filters(**self._last_filters)

    def sort_documents(
            self,
            documents: List[DocumentRecord],
            sort_mode: str
    ) -> List[DocumentRecord]:
        """
        Sort document list. 

        Args:
            documents: List to sort
            sort_mode: "updated" | "status" | "title"

        Returns: 
            Sorted list
        """
        mode = (sort_mode or "").lower()

        if mode.startswith("status"):
            # Status workflow order
            order = {
                DocumentStatus.DRAFT: 0,
                DocumentStatus.REVIEW: 1,
                DocumentStatus.APPROVED: 2,
                DocumentStatus.EFFECTIVE: 3,
                DocumentStatus.REVISION: 4,
                DocumentStatus.OBSOLETE: 5,
                DocumentStatus.ARCHIVED: 6,
            }
            return sorted(documents, key=lambda r: order.get(r.status, 99))

        elif mode.startswith("titel") or mode.startswith("title"):
            # Alphabetical by title
            return sorted(documents, key=lambda r: (r.title or "").lower())

        else:
            # Default: updated desc
            return sorted(documents, key=lambda r: (r.updated_at or ""), reverse=True)