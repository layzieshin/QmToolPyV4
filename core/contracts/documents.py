"""core/contracts/documents.py
==========================

Document-related contracts (repositories/services) used across features.

The repo currently has concrete repositories inside the `documents` feature.
This interface exists to avoid direct feature-to-feature imports later.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterable, Optional


class IDocumentRepository(ABC):
    """Persistence API for documents (minimal, extendable)."""

    @abstractmethod
    def list_documents(self) -> Iterable[Any]:
        """Return an iterable of document items."""

    @abstractmethod
    def get_document(self, document_id: str) -> Optional[Any]:
        """Return a single document item by id."""

    @abstractmethod
    def save_document(self, document: Any) -> None:
        """Persist document data."""
