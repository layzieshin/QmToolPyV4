"""SearchFilterController - handles search and filter logic."""

from __future__ import annotations
from typing import List, Optional
import logging

from documents.models. document_models import DocumentRecord, DocumentStatus

logger = logging.getLogger(__name__)


class SearchFilterController:
    """
    Stateless controller for search and filter operations.

    Responsibilities:
    - Apply search/status/active filters
    - Sort document lists

    SRP:  No UI, no workflow logic, only data filtering.
    """

    def __init__(self, *, repository) -> None:
        """
        Args:
            repository: Documents repository for data access
        """
        self._repo = repository
        self._last_filters = {
            "text": None,
            "status":  None,
            "active_only": False,
        }

    def apply_filters(
            self,
            *,
            text: Optional[str] = None,
            status:  Optional[DocumentStatus] = None,
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

        try:
            # Delegate to repository
            return self._repo.list(
                status=status,
                text=text,
                active_only=active_only
            )
        except TypeError as ex:
            # Fallback for repos that don't support all filter kwargs
            logger.warning(
                f"Repository. list() does not support full filter API: {ex}.  "
                "Falling back to status-only filtering with in-memory post-filter."
            )
            return self._fallback_filter(text=text, status=status, active_only=active_only)
        except Exception as ex:
            logger.error(f"Error during list operation: {ex}")
            return []

    def _fallback_filter(
            self,
            *,
            text: Optional[str],
            status: Optional[DocumentStatus],
            active_only: bool
    ) -> List[DocumentRecord]:
        """Fallback in-memory filtering if repo doesn't support full API."""
        try:
            # Try with status only
            docs = self._repo.list(status=status)
        except Exception:
            try:
                docs = self._repo.list()
            except Exception:
                return []

        # Apply text filter in memory
        if text and text.strip():
            search_lower = text.strip().lower()
            docs = [
                d for d in docs
                if search_lower in (d.title or "").lower()
                or search_lower in (getattr(d, "doc_code", "") or "").lower()
                or search_lower in str(getattr(d. doc_id, "value", d.doc_id)).lower()
            ]

        # Apply active_only filter in memory (if repo provides is_workflow_active)
        if active_only:
            filtered = []
            for d in docs:
                try:
                    doc_id_str = getattr(d. doc_id, "value", str(d.doc_id))
                    if self._repo.is_workflow_active(doc_id_str):
                        filtered. append(d)
                except Exception:
                    pass  # Skip if method not available
            docs = filtered

        return docs

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
            documents:  List to sort
            sort_mode: "updated" | "status" | "title"

        Returns:
            Sorted list
        """
        mode = (sort_mode or "").lower()

        if mode. startswith("status"):
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
            # Default:  updated desc
            return sorted(documents, key=lambda r: (r.updated_at or ""), reverse=True)