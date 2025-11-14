"""
===============================================================================
Comment Repository Protocol – read/write contract for comments
-------------------------------------------------------------------------------
Purpose:
    Provide a minimal interface for listing and adding comments associated with
    a document. Storage can be SQLite or extracted-on-demand (future).

Design:
    - Smallest viable methods for the current UI.
    - Threading and edit/delete will be added later if needed.
===============================================================================
"""
from __future__ import annotations
from typing import Protocol, List

from documentlifecycle.models.comment import Comment


class CommentRepository(Protocol):
    """
    Read/write contract for document comments.

    Methods
    -------
    list_for_document(doc_id) -> list[Comment]
        Return recent comments descending by timestamp.
    add(comment) -> None
        Persist a new comment.
    """

    def list_for_document(self, doc_id: int) -> List[Comment]:
        ...

    def add(self, comment: Comment) -> None:
        ...
