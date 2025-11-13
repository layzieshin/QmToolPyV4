"""
===============================================================================
Document Repository Protocol – read access contract
-------------------------------------------------------------------------------
Purpose:
    Define the minimal read-only contract for fetching documents for the
    lifecycle module. Concrete implementations may use SQLite, files, or HTTP.

Design:
    - Protocol only; no implementation details.
    - Pure read side for M1/M2; write methods can be added in later milestones.
===============================================================================
"""
from __future__ import annotations
from typing import Protocol, Optional, List
from datetime import datetime

from documentlifecycle.models.document import Document
from documentlifecycle.models.document_status import DocumentStatus
from documentlifecycle.models.document_type import DocumentType


class DocumentRepository(Protocol):
    """
    Read contract for lifecycle documents.

    Methods
    -------
    search(query, status, doc_type, last_action_since) -> list[Document]
        Apply optional filters. Implementations should sort by
        last activity desc (updated/created).
    get_by_id(doc_id) -> Optional[Document]
        Return a single document or None.
    """

    def search(
        self,
        query: str | None,
        status: Optional[DocumentStatus] = None,
        doc_type: Optional[DocumentType] = None,
        last_action_since: Optional[datetime] = None
    ) -> List[Document]:
        ...

    def get_by_id(self, doc_id: int) -> Optional[Document]:
        ...
