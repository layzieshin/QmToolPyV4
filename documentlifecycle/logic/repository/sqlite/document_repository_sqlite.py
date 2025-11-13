"""
===============================================================================
DocumentRepositorySQLite – SQLite-backed repository (read/write)
-------------------------------------------------------------------------------
Includes helpers for versioning and code existence checks.
===============================================================================
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List
import sqlite3
import re

from .base_sqlite_repo import BaseSQLiteRepo
from documentlifecycle.models.document import Document
from documentlifecycle.models.document_status import DocumentStatus
from documentlifecycle.models.document_type import DocumentType
from documentlifecycle.models.assigned_roles import AssignedRoles


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            code TEXT,
            description TEXT,
            doc_type TEXT NOT NULL,
            status TEXT NOT NULL,
            version_label TEXT,
            revision INTEGER NOT NULL DEFAULT 0,
            file_path TEXT,
            created_at TEXT,
            updated_at TEXT,
            edited_at TEXT,
            reviewed_at TEXT,
            published_at TEXT,
            valid_from TEXT,
            valid_until TEXT,
            archived_at TEXT,
            archived_by INTEGER,
            archive_reason TEXT
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS document_roles (
            document_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            note TEXT,
            PRIMARY KEY (document_id, user_id, role),
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        );
        """
    )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(documents)").fetchall()}
    if "code" not in cols:
        conn.execute("ALTER TABLE documents ADD COLUMN code TEXT;")
    conn.commit()


def _parse_dt(txt: Optional[str]) -> Optional[datetime]:
    if not txt:
        return None
    try:
        return datetime.fromisoformat(txt)
    except Exception:
        try:
            return datetime.strptime(txt, "%Y-%m-%d")
        except Exception:
            return None


class DocumentRepositorySQLite(BaseSQLiteRepo):
    def __init__(self) -> None:
        super().__init__(None)
        _ensure_schema(self.conn)

    # --------------- mapping --------------- #
    def _row_to_model(self, r: sqlite3.Row) -> Document:
        roles = AssignedRoles(editor_id=None, reviewer_id=None, publisher_id=None)
        try:
            dt = DocumentType(r["doc_type"]) if r["doc_type"] else DocumentType.OTHER
        except Exception:
            dt = DocumentType.OTHER
        try:
            st = DocumentStatus(r["status"]) if r["status"] else DocumentStatus.DRAFT
        except Exception:
            st = DocumentStatus.DRAFT

        return Document(
            id=int(r["id"]),
            title=r["title"],
            description=r["description"] or "",
            doc_type=dt,
            status=st,
            version_label=r["version_label"] or "1.0",
            revision=int(r["revision"] or 0),
            file_path=r["file_path"] or "",
            roles=roles,
            created_at=_parse_dt(r["created_at"]),
            updated_at=_parse_dt(r["updated_at"]),
            edited_at=_parse_dt(r["edited_at"]),
            reviewed_at=_parse_dt(r["reviewed_at"]),
            published_at=_parse_dt(r["published_at"]),
            valid_from=_parse_dt(r["valid_from"]),
            valid_until=_parse_dt(r["valid_until"]),
            archived_at=_parse_dt(r["archived_at"]),
            archived_by=int(r["archived_by"]) if r["archived_by"] is not None else None,
            archive_reason=r["archive_reason"],
        )

    # --------------- READ --------------- #
    def search(self, query, status=None, doc_type=None, last_action_since=None) -> List[Document]:
        q = "SELECT * FROM documents WHERE 1=1"
        params: list = []
        if query:
            like = f"%{query}%"
            q += " AND (title LIKE ? OR description LIKE ? OR code LIKE ?)"
            params += [like, like, like]
        if status:
            q += " AND status = ?"; params.append(status.value)
        if doc_type:
            q += " AND doc_type = ?"; params.append(doc_type.value)
        if last_action_since:
            iso = last_action_since.isoformat()
            q += " AND (updated_at >= ? OR edited_at >= ? OR reviewed_at >= ? OR published_at >= ?)"
            params += [iso, iso, iso, iso]
        q += " ORDER BY COALESCE(updated_at, created_at) DESC"
        rows = self.conn.execute(q, params).fetchall()
        return [self._row_to_model(r) for r in rows]

    def get_by_id(self, doc_id: int) -> Optional[Document]:
        r = self.conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return self._row_to_model(r) if r else None

    def get_code_for_id(self, doc_id: int) -> Optional[str]:
        r = self.conn.execute("SELECT code FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if not r:
            return None
        try:
            return r["code"]  # type: ignore[index]
        except Exception:
            return r[0] if r[0] is not None else None

    def get_file_path(self, doc_id: int) -> Optional[str]:
        r = self.conn.execute("SELECT file_path FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if not r:
            return None
        try:
            return r["file_path"]  # type: ignore[index]
        except Exception:
            return r[0] if r[0] is not None else None

    # --------------- WRITE --------------- #
    def create_from_file(
        self, *, title: str, doc_type, user_id: Optional[int], src_file: str,
        status="DRAFT", description: str = "", code: Optional[str] = None,
        version_label: str = "1.0", revision: int = 0
    ) -> int:
        # normalize doc_type/status
        try:
            doc_type_val = doc_type.value if isinstance(doc_type, DocumentType) else DocumentType[doc_type].value
        except Exception:
            try:
                _ = DocumentType(doc_type); doc_type_val = doc_type
            except Exception:
                doc_type_val = DocumentType.OTHER.value
        try:
            status_val = status.value if isinstance(status, DocumentStatus) else DocumentStatus[status].value
        except Exception:
            try:
                _ = DocumentStatus(status); status_val = status
            except Exception:
                status_val = DocumentStatus.DRAFT.value

        now = datetime.utcnow().isoformat(timespec="seconds")
        cur = self.conn.execute(
            """
            INSERT INTO documents
            (title, code, description, doc_type, status, version_label, revision,
             file_path, created_at, updated_at, edited_at, reviewed_at,
             published_at, valid_from, valid_until, archived_at, archived_by, archive_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (title, code, description, doc_type_val, status_val,
             version_label, revision, src_file, now, now, None, None, None, None, None, None, None, None),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def update_metadata(self, *, doc_id: int, title: str, code: Optional[str], doc_type, description: str = "") -> None:
        try:
            doc_type_val = doc_type.value if isinstance(doc_type, DocumentType) else DocumentType[doc_type].value
        except Exception:
            try:
                _ = DocumentType(doc_type); doc_type_val = doc_type
            except Exception:
                doc_type_val = DocumentType.OTHER.value
        now = datetime.utcnow().isoformat(timespec="seconds")
        self.conn.execute(
            "UPDATE documents SET title=?, code=?, description=?, doc_type=?, updated_at=? WHERE id=?",
            (title, code, description, doc_type_val, now, doc_id),
        )
        self.conn.commit()

    def update_status(self, *, doc_id: int, new_status) -> None:
        try:
            status_val = new_status.value if isinstance(new_status, DocumentStatus) else DocumentStatus[new_status].value
        except Exception:
            try:
                _ = DocumentStatus(new_status); status_val = new_status
            except Exception:
                status_val = DocumentStatus.DRAFT.value
        now = datetime.utcnow().isoformat(timespec="seconds")
        self.conn.execute(
            "UPDATE documents SET status=?, updated_at=? WHERE id=?",
            (status_val, now, doc_id),
        )
        self.conn.commit()

    def archive(self, *, doc_id: int, archived_by: Optional[int], reason: str | None = None) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        self.conn.execute(
            """
            UPDATE documents
               SET status=?, archived_at=?, archived_by=?, archive_reason=?, updated_at=?
             WHERE id=?
            """,
            ("ARCHIVED", now, archived_by, reason, now, doc_id),
        )
        self.conn.commit()

    def update_file_path(self, *, doc_id: int, new_path: str) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        self.conn.execute(
            "UPDATE documents SET file_path=?, updated_at=? WHERE id=?",
            (new_path, now, doc_id),
        )
        self.conn.commit()

    # --------------- version/code helpers --------------- #
    def exists_any_with_code(self, code: str) -> bool:
        r = self.conn.execute("SELECT 1 FROM documents WHERE code = ? LIMIT 1", (code,)).fetchone()
        return bool(r)

    def get_latest_by_code(self, code: str) -> Optional[Document]:
        r = self.conn.execute(
            "SELECT * FROM documents WHERE code=? ORDER BY created_at DESC, id DESC LIMIT 1",
            (code,)
        ).fetchone()
        return self._row_to_model(r) if r else None

    def get_latest_published_by_code(self, code: str) -> Optional[Document]:
        r = self.conn.execute(
            "SELECT * FROM documents WHERE code=? AND status IN ('RELEASED','PUBLISHED') "
            "ORDER BY published_at DESC, updated_at DESC, id DESC LIMIT 1",
            (code,)
        ).fetchone()
        return self._row_to_model(r) if r else None

    def get_next_version_label(self, code: str) -> str:
        """
        Compute next major version like '1.0' -> '2.0' -> '3.0'.
        If no version exists, start with '1.0'.
        """
        r = self.conn.execute(
            "SELECT version_label FROM documents WHERE code=? ORDER BY created_at DESC, id DESC LIMIT 1",
            (code,)
        ).fetchone()
        if not r:
            return "1.0"
        try:
            v = r["version_label"] if isinstance(r, sqlite3.Row) else r[0]
            m = re.match(r"^\s*(\d+)\.(\d+)\s*$", v or "")
            if not m:
                return "1.0"
            major = int(m.group(1)) + 1
            return f"{major}.0"
        except Exception:
            return "1.0"
