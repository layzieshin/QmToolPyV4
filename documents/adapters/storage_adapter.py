"""Storage adapter abstraction.

TODO: Define interface for workflow/published storage operations.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class StorageAdapter(ABC):
    """Abstract storage adapter for document content."""

    @abstractmethod
    def save_working_copy(self, *, doc_id: str, path: str) -> None:
        """Persist a working copy."""
        raise NotImplementedError
