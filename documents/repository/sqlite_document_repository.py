"""SQLite implementation of DocumentRepository.

Lightweight repository - only CRUD and simple queries.
Business logic is in services layer.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from documents.adapters.sqlite_adapter import SQLiteAdapter
from documents.logic.id_generator import IdGenerator
from documents.models.document_models import DocumentId, DocumentRecord, DocumentStatus
from documents.repository.repo_config import RepoConfig


class SQLiteDocumentRepository:
    """SQLite backend for documents.

    Note (Option A):
    - Repository is DB-only.
    - Any file storage/copy/move is handled outside of the repository.
    """

    def __init__(self, config: RepoConfig, *, db_adapter: Optional[Any] = None) -> None:
        """
        Args:
            config: Repository configuration
            db_adapter: Database adapter (default: SQLiteAdapter)
        """
        self._cfg = config
        self._db = db_adapter or SQLiteAdapter(config.db_path)

        self._ensure_schema()
        self._id_gen = IdGenerator(self._db, config.id_prefix, config.id_pattern)

    def _ensure_schema(self) -> None:
        """Create database schema if not exists."""
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                doc_type TEXT NOT NULL,
                status TEXT NOT NULL,
                version_major INTEGER NOT NULL,
                version_minor INTEGER NOT NULL,
                current_file_path TEXT,
                doc_code TEXT,
                created_by TEXT,
                created_at TEXT,
                updated_at TEXT,
                next_review TEXT
            );

            CREATE TABLE IF NOT EXISTS workflow_state (
                doc_id TEXT PRIMARY KEY,
                workflow_active INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id TEXT NOT NULL,
                role TEXT NOT NULL,
                username TEXT NOT NULL,
                assigned_at TEXT,
                UNIQUE(doc_id, role, username)
            );

            CREATE TABLE IF NOT EXISTS signatures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id TEXT NOT NULL,
                role TEXT NOT NULL,
                username TEXT NOT NULL,
                signed_at TEXT,
                comment TEXT
            );
            """
        )

    def create(
        self,
        *,
        title: str,
        doc_type: str,
        user_id: str,
        file_path: str,
        doc_code: Optional[str] = None,
    ) -> DocumentRecord:
        """Create new document record.

        Defensive behavior:
        - If doc_id generation collides with an existing ID (UNIQUE constraint),
          retry a few times with a newly generated ID.
        """
        now = datetime.utcnow().isoformat(timespec="seconds")
        next_review = (
            datetime.utcnow() + timedelta(days=30 * self._cfg.review_months)
        ).isoformat(timespec="seconds")

        last_exc: Optional[Exception] = None

        for _ in range(5):
            doc_id = self._id_gen.next_id()
            try:
                self._db.insert(
                    "documents",
                    {
                        "doc_id": doc_id,
                        "title": title,
                        "doc_type": doc_type,
                        # Store Enum name to match DocumentStatus[row["status"]] usage.
                        "status": DocumentStatus.DRAFT.name,
                        "version_major": 1,
                        "version_minor": 0,
                        "current_file_path": file_path,
                        "doc_code": doc_code,
                        "created_by": user_id,
                        "created_at": now,
                        "updated_at": now,
                        "next_review": next_review,
                    },
                )

                # Initialize workflow state
                self._db.insert(
                    "workflow_state", {"doc_id": doc_id, "workflow_active": 0}
                )

                rec = self.get(doc_id)
                if rec is None:
                    raise RuntimeError("Document was inserted but could not be reloaded.")
                return rec

            except sqlite3.IntegrityError as ex:
                msg = str(ex).lower()
                if "unique constraint failed" in msg and "documents.doc_id" in msg:
                    last_exc = ex
                    continue
                raise

            except Exception as ex:
                msg = str(ex).lower()
                if "unique constraint failed" in msg and "documents.doc_id" in msg:
                    last_exc = ex
                    continue
                raise

        raise RuntimeError(
            f"Failed to create document after retries due to duplicate doc_id: {last_exc}"
        )

    def create_from_file(
        self,
        *,
        title: Optional[str],
        doc_type: str,
        user_id: str,
        src_file: str,
    ) -> DocumentRecord:
        """Create new document record from an existing DOCX file.

        Option A (DB-only repository):
        - We store the provided source path as the current_file_path and do not copy/move the file.
        - File storage concerns must be handled by a higher layer/service.
        """
        if title is None:
            base = os.path.basename(src_file)
            title = os.path.splitext(base)[0]

        return self.create(
            title=title,
            doc_type=doc_type,
            user_id=user_id,
            file_path=src_file,
        )

    def get(self, doc_id: str) -> Optional[DocumentRecord]:
        """Get document by ID."""
        row = self._db.fetchone("SELECT * FROM documents WHERE doc_id=?", (doc_id,))
        if not row:
            return None
        return self._row_to_record(row)

    def list(self, *, status: Optional[DocumentStatus] = None) -> List[DocumentRecord]:
        """List documents, optionally filtered by status."""
        sql = "SELECT * FROM documents"
        params: List[Any] = []

        if status is not None:
            sql += " WHERE status = ?"
            params.append(status.name)

        sql += " ORDER BY updated_at DESC"
        rows = self._db.fetchall(sql, tuple(params)) or []
        return [self._row_to_record(r) for r in rows]

    def list_comments(self, doc_id: str) -> List[Dict[str, Any]]:
        """Return extracted DOCX comments for the current document file.

        Option A (DB-only repository):
        - We do not manage storage. We only read comments from the current file path
          stored in the document record (if available).
        - If the file is missing or not a .docx, returns [].

        Returns dicts with keys: version_label, author, date, text.
        """
        rec = self.get(doc_id)
        if rec is None:
            return []

        path = getattr(rec, "current_file_path", None) or getattr(rec, "file_path", None)
        if not path or not isinstance(path, str):
            return []

        if not path.lower().endswith(".docx"):
            return []

        if not os.path.exists(path):
            return []

        try:
            from word_meta.logic.docx_comments_reader import read_docx_comments  # type: ignore
        except Exception:
            return []

        try:
            comments = read_docx_comments(path)
        except Exception:
            return []

        out: List[Dict[str, Any]] = []
        for c in comments:
            dt = getattr(c, "date", None)
            out.append(
                {
                    "version_label": "",
                    "author": getattr(c, "author", "") or "",
                    "date": dt.isoformat(sep=" ", timespec="seconds") if dt else "",
                    "text": getattr(c, "text", "") or "",
                }
            )

        return out

    def _row_to_record(self, row: Dict[str, Any]) -> DocumentRecord:
        """Convert DB row into DocumentRecord."""
        doc_id = DocumentId(row["doc_id"])
        status = DocumentStatus[row["status"]]

        return DocumentRecord(
            doc_id=doc_id,
            title=row.get("title", ""),
            doc_type=row.get("doc_type", ""),
            status=status,
            version_major=int(row.get("version_major") or 1),
            version_minor=int(row.get("version_minor") or 0),
            current_file_path=row.get("current_file_path"),
            doc_code=row.get("doc_code"),
            created_by=row.get("created_by"),
            created_at=self._parse_dt(row.get("created_at")),
            updated_at=self._parse_dt(row.get("updated_at")),
            next_review=self._parse_dt(row.get("next_review")),
        )

    @staticmethod
    def _parse_dt(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None
