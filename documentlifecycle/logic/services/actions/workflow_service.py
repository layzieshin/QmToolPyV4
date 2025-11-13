"""
===============================================================================
WorkflowService – State transitions with repository persistence
-------------------------------------------------------------------------------
Transitions (current MVP placeholders; rules/policies will be added later):
    - start      -> IN_EDIT (fallback IN_REVIEW)
    - cancel     -> DRAFT
    - finishSign -> IN_REVIEW
    - archive    -> archived + metadata

Collaborators
    - DocumentRepositorySQLite
    - (future) AuthorizationService / LifecycleEngine for strict policies.
===============================================================================
"""
from __future__ import annotations

from typing import Optional

from documentlifecycle.logic.repository.sqlite.document_repository_sqlite import DocumentRepositorySQLite


class WorkflowService:
    """Encapsulates lifecycle transitions and persistence."""

    def __init__(self) -> None:
        self._repo = DocumentRepositorySQLite()

    def start(self, *, document_id: int) -> None:
        try:
            self._repo.update_status(doc_id=document_id, new_status="IN_EDIT")
        except Exception:
            self._repo.update_status(doc_id=document_id, new_status="IN_REVIEW")

    def cancel(self, *, document_id: int) -> None:
        self._repo.update_status(doc_id=document_id, new_status="DRAFT")

    def finish_and_sign(self, *, document_id: int) -> None:
            # placeholder → later: docx→pdf + signature + transition rules
            self._repo.update_status(doc_id=document_id, new_status="IN_REVIEW")


    def archive(self, *, document_id: int, archived_by: Optional[int]) -> None:
        self._repo.archive(doc_id=document_id, archived_by=archived_by, reason=None)
