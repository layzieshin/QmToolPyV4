"""
===============================================================================
CommentRepositorySQLite – SQLite-backed comment storage
-------------------------------------------------------------------------------
Purpose:
    Provide minimal persistence for comments associated with documents.
    The table is created on first use. This module supports listing and
    inserting only (M1/M2 scope).

Design:
    - Timestamps are stored as ISO8601 strings.
    - Returns newest comments first for convenient display.
===============================================================================
"""
from __future__ import annotations
from datetime import datetime
from typing import List
import sqlite3

from .base_sqlite_repo import BaseSQLiteRepo
from documentlifecycle.models.comment import Comment
from documentlifecycle.models.comment_type import CommentType

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL,
        author_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        type TEXT NOT NULL DEFAULT 'General',
        text TEXT NOT NULL,
        related_version TEXT,
        FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
    );
    """
]


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create minimal comments table if it does not exist yet."""
    for ddl in _DDL:
        conn.execute(ddl)
    conn.commit()


def _parse_dt(txt: str) -> datetime:
    """Parse an ISO8601 timestamp; fallback to UTC now on failure."""
    try:
        return datetime.fromisoformat(txt)
    except Exception:
        return datetime.utcnow()


class CommentRepositorySQLite(BaseSQLiteRepo):
    """
    SQLite implementation of CommentRepository.

    Methods
    -------
    list_for_document(doc_id) -> list[Comment]
        Return the newest comments first.
    add(comment) -> None
        Insert a new comment (auto-assigns id).
    """

    def __init__(self) -> None:
        super().__init__(None)
        _ensure_schema(self.conn)

    def list_for_document(self, doc_id: int) -> List[Comment]:
        """Return comments for a document (descending by created_at)."""
        cur = self.conn.execute(
            "SELECT id, document_id, author_id, created_at, type, text, related_version "
            "FROM comments WHERE document_id=? ORDER BY created_at DESC",
            (doc_id,)
        )
        rows = cur.fetchall()
        out: List[Comment] = []
        for r in rows:
            out.append(Comment(
                id=int(r["id"]),
                document_id=int(r["document_id"]),
                author_id=int(r["author_id"]),
                created_at=_parse_dt(r["created_at"]),
                text=r["text"] or "",
                ctype=CommentType(r["type"]) if r["type"] else CommentType.GENERAL,
                related_version=r["related_version"]
            ))
        return out

    def add(self, comment: Comment) -> None:
        """Insert a new comment and commit the change."""
        self.conn.execute(
            "INSERT INTO comments(document_id, author_id, created_at, type, text, related_version) VALUES (?,?,?,?,?,?)",
            (comment.document_id, comment.author_id, (comment.created_at or datetime.utcnow()).isoformat(),
             comment.ctype.value, comment.text, comment.related_version)
        )
        self.conn.commit()
