"""
===============================================================================
CommentService – read/write adapter for document comments
-------------------------------------------------------------------------------
Purpose:
    Provide a small, UI-oriented layer to:
      - list comments for a document,
      - add a new comment (placeholder-level validation).

Non-Goals:
    - No threading/mentions/reactions in this milestone.
    - No heavy moderation; only minimal whitespace checks.

Integration:
    - Consumed by controllers later (when comment UI is wired).
    - Author display strings are provided via a callback to avoid direct
      coupling to the host user repository.
===============================================================================
"""
from __future__ import annotations
from typing import List, Dict, Callable, Optional
from datetime import datetime

from documentlifecycle.logic.repository.comment_repository import CommentRepository
from documentlifecycle.models.comment import Comment
from documentlifecycle.models.comment_type import CommentType

# Optional project logger; must not break even if signature differs
try:
    from core.logging.logic.logger import logger  # type: ignore
except Exception:  # pragma: no cover
    class _NoopLogger:
        def log(self, *args, **kwargs) -> None:
            pass
    logger = _NoopLogger()  # type: ignore


class CommentService:
    """
    UI-facing comment adapter.

    Parameters
    ----------
    repo : CommentRepository
        Storage backend (SQLite or other).
    resolve_user_display : Callable[[int | None], str]
        Callback to map author_id to a display name in the UI.
    """

    def __init__(self, repo: CommentRepository, resolve_user_display: Callable[[int | None], str]) -> None:
        self._repo = repo
        self._resolve = resolve_user_display

    # ------------------------------------------------------------------ #
    # Internal robust logging (positional args only)
    # ------------------------------------------------------------------ #
    def _safe_log(self, source: str, action: str, **fields) -> None:
        try:
            msg = " | ".join(f"{k}={v}" for k, v in fields.items())
            try:
                logger.log(source, action, msg)  # type: ignore[arg-type]
            except TypeError:
                logger.log(source, action, msg, None)  # type: ignore[arg-type]
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Use cases
    # ------------------------------------------------------------------ #
    def list_comments(self, document_id: int) -> List[Dict]:
        """
        Return newest-first comment dicts for rendering.

        Returns
        -------
        list[dict]
            Fields: id, author, created_at, type, text, related_version
        """
        items = self._repo.list_for_document(document_id)
        rows: List[Dict] = []
        for c in items:
            rows.append({
                "id": c.id,
                "author": self._resolve(c.author_id),
                "created_at": (c.created_at or datetime.utcnow()).isoformat(sep=" ", timespec="seconds"),
                "type": c.ctype.value,
                "text": c.text,
                "related_version": c.related_version or "",
            })
        self._safe_log("CommentService", "List", count=len(rows), doc=document_id)
        return rows

    def add_comment(
        self,
        *,
        document_id: int,
        author_id: int,
        text: str,
        ctype: CommentType = CommentType.GENERAL,
        related_version: Optional[str] = None
    ) -> None:
        """
        Insert a new comment. Minimal validation only.

        Raises
        ------
        ValueError
            If text is empty after stripping whitespace.
        """
        if not text or not text.strip():
            raise ValueError("Comment text must not be empty.")

        comment = Comment(
            id=None,
            document_id=document_id,
            author_id=author_id,
            created_at=datetime.utcnow(),
            text=text.strip(),
            ctype=ctype,
            related_version=related_version
        )
        self._repo.add(comment)
        self._safe_log("CommentService", "Add", doc=document_id, author=author_id)
