"""SQLite implementation of DocumentRepository.

Lightweight repository - only CRUD and simple queries.
Business logic is in services layer.
"""

from __future__ import annotations
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
import os

from documents.repository.repo_config import RepoConfig
from documents.models.document_models import DocumentRecord, DocumentStatus, DocumentId

# Adapters
from documents.adapters.database_adapter import DatabaseAdapter
from documents.adapters.sqlite_adapter import SQLiteAdapter

# Utilities
from documents.logic.id_generator import IdGenerator


class SQLiteDocumentRepository:
    """
    Lightweight SQLite document repository.

    Responsibilities:
    - CRUD operations
    - Simple queries
    - Metadata updates
    - Workflow state
    - Assignments

    NOT responsible for:
    - PDF generation (→ PDFService)
    - Version logic (→ VersionService)
    - Business rules (→ Controllers/Policies)
    """

    def __init__(
        self,
        config: RepoConfig,
        *,
        db_adapter: Optional[DatabaseAdapter] = None
    ):
        """
        Initialize repository.

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
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                doc_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'DRAFT',
                version_major INTEGER NOT NULL DEFAULT 1,
                version_minor INTEGER NOT NULL DEFAULT 0,
                current_file_path TEXT,
                doc_code TEXT,
                area TEXT,
                process TEXT,
                valid_from TEXT,
                next_review TEXT,
                obsoleted_at TEXT,
                created_by TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                change_note TEXT,
                locked_by TEXT,
                locked_at TEXT
            );
            
            CREATE TABLE IF NOT EXISTS workflow_state (
                doc_id TEXT PRIMARY KEY,
                workflow_active INTEGER NOT NULL DEFAULT 0,
                workflow_started_by TEXT,
                workflow_started_at TEXT,
                FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
            );
            
            CREATE TABLE IF NOT EXISTS assignments (
                doc_id TEXT NOT NULL,
                role TEXT NOT NULL,
                user_id TEXT NOT NULL,
                PRIMARY KEY (doc_id, role, user_id),
                FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
            );
            
            CREATE TABLE IF NOT EXISTS signatures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id TEXT NOT NULL,
                step TEXT NOT NULL,
                user_id TEXT NOT NULL,
                signed_at TEXT NOT NULL,
                reason TEXT,
                pdf_path TEXT,
                FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
            );
            
            CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
            CREATE INDEX IF NOT EXISTS idx_documents_updated ON documents(updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_workflow_active ON workflow_state(workflow_active);
        """)

    # ===== CRUD OPERATIONS =====

    def create(
        self,
        *,
        title: str,
        doc_type: str,
        user_id: str,
        file_path: str,
        doc_code: Optional[str] = None
    ) -> DocumentRecord:
        """Create new document record."""
        doc_id = self._id_gen.next_id()
        now = datetime.utcnow().isoformat(timespec="seconds")
        next_review = (datetime.utcnow() + timedelta(days=30 * self._cfg.review_months)).isoformat(timespec="seconds")

        self._db.insert("documents", {
            "doc_id": doc_id,
            "title": title,
            "doc_type": doc_type,
            "status": DocumentStatus.DRAFT.name,
            "version_major":  1,
            "version_minor": 0,
            "current_file_path": file_path,
            "doc_code": doc_code,
            "created_by": user_id,
            "created_at": now,
            "updated_at": now,
            "next_review": next_review
        })

        # Initialize workflow state
        self._db.insert("workflow_state", {"doc_id": doc_id, "workflow_active": 0})

        return self.get(doc_id)  # type: ignore

    def get(self, doc_id: str) -> Optional[DocumentRecord]:
        """Get document by ID."""
        row = self._db.fetchone("SELECT * FROM documents WHERE doc_id = ?", (doc_id,))
        return self._row_to_record(row) if row else None

    def list(
        self,
        *,
        status: Optional[DocumentStatus] = None,
        text:  Optional[str] = None,
        active_only: bool = False
    ) -> List[DocumentRecord]:
        """List documents with filters."""
        query = "SELECT * FROM documents WHERE 1=1"
        params:  List[Any] = []

        if status:
            query += " AND status = ?"
            params.append(status.name)

        if text:
            query += " AND (doc_id LIKE ?  OR title LIKE ? )"
            search = f"%{text}%"
            params.extend([search, search])

        if active_only:
            query += " AND doc_id IN (SELECT doc_id FROM workflow_state WHERE workflow_active = 1)"

        query += " ORDER BY updated_at DESC"

        rows = self._db.fetchall(query, tuple(params))
        return [self._row_to_record(row) for row in rows]

    def update_metadata(self, doc_id: str, data: Dict[str, Any]) -> None:
        """Update document metadata."""
        allowed = {"title", "doc_type", "area", "process", "next_review", "change_note"}
        updates = {k: v for k, v in data.items() if k in allowed}

        if updates:
            updates["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
            self._db.update("documents", updates, "doc_id = ?", (doc_id,))

    def update_file_path(self, doc_id: str, file_path: str) -> None:
        """Update current file path."""
        self._db.update(
            "documents",
            {"current_file_path": file_path, "updated_at": datetime.utcnow().isoformat(timespec="seconds")},
            "doc_id = ? ",
            (doc_id,)
        )

    def update_version(self, doc_id: str, major: int, minor: int) -> None:
        """Update version numbers."""
        self._db.update(
            "documents",
            {"version_major": major, "version_minor": minor, "updated_at": datetime.utcnow().isoformat(timespec="seconds")},
            "doc_id = ?",
            (doc_id,)
        )

    def set_status(self, doc_id: str, status: DocumentStatus, reason: Optional[str] = None) -> None:
        """Change document status."""
        updates = {
            "status": status.name,
            "updated_at":  datetime.utcnow().isoformat(timespec="seconds")
        }

        if reason:
            updates["change_note"] = reason

        if status == DocumentStatus.OBSOLETE:
            updates["obsoleted_at"] = datetime.utcnow().isoformat(timespec="seconds")

        self._db.update("documents", updates, "doc_id = ?", (doc_id,))

    # ===== WORKFLOW STATE =====

    def is_workflow_active(self, doc_id: str) -> bool:
        """Check if workflow is active."""
        row = self._db.fetchone("SELECT workflow_active FROM workflow_state WHERE doc_id = ?", (doc_id,))
        return bool(row["workflow_active"]) if row else False

    def set_workflow_active(self, doc_id: str, active: bool, started_by: Optional[str] = None) -> None:
        """Set workflow active state."""
        now = datetime.utcnow().isoformat(timespec="seconds")

        self._db.execute("""
            INSERT INTO workflow_state (doc_id, workflow_active, workflow_started_by, workflow_started_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(doc_id) DO UPDATE SET
                workflow_active = excluded.workflow_active,
                workflow_started_by = excluded.workflow_started_by,
                workflow_started_at = excluded.workflow_started_at
        """, (doc_id, int(active), started_by, now if active else None))

        self._db.commit()

    def get_workflow_starter(self, doc_id: str) -> Optional[str]:
        """Get user who started workflow."""
        row = self._db.fetchone("SELECT workflow_started_by FROM workflow_state WHERE doc_id = ?", (doc_id,))
        return row["workflow_started_by"] if row else None

    # ===== ASSIGNMENTS =====

    def get_assignees(self, doc_id:  str) -> Dict[str, List[str]]:
        """Get role assignments."""
        rows = self._db.fetchall("SELECT role, user_id FROM assignments WHERE doc_id = ?  ORDER BY role, user_id", (doc_id,))

        result: Dict[str, List[str]] = {"AUTHOR": [], "REVIEWER": [], "APPROVER": []}

        for row in rows:
            role = str(row["role"]).upper()
            if role in result:
                result[role].append(str(row["user_id"]))

        return result

    def set_assignees(self, doc_id: str, mapping: Dict[str, List[str]]) -> None:
        """Set role assignments."""
        self._db.execute("DELETE FROM assignments WHERE doc_id = ?", (doc_id,))

        for role, users in mapping.items():
            for user_id in (users or []):
                if user_id:
                    self._db.execute(
                        "INSERT INTO assignments (doc_id, role, user_id) VALUES (?, ?, ?)",
                        (doc_id, role.upper(), user_id)
                    )

        self._db.commit()

    def get_owner(self, doc_id: str) -> Optional[str]:
        """Get document owner."""
        row = self._db.fetchone("SELECT created_by FROM documents WHERE doc_id = ?", (doc_id,))
        if row and row["created_by"]:
            return row["created_by"]

        # Fallback:  first author
        assignees = self.get_assignees(doc_id)
        authors = assignees.get("AUTHOR", [])
        return authors[0] if authors else None

    # ===== SIGNATURES =====

    def record_signature(self, doc_id: str, step: str, user_id: str, pdf_path: str, reason: Optional[str] = None) -> None:
        """Record a signature event."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        self._db.insert("signatures", {
            "doc_id": doc_id,
            "step": step,
            "user_id": user_id,
            "signed_at": now,
            "reason": reason,
            "pdf_path": pdf_path
        })

    def get_signatures(self, doc_id: str) -> List[Dict[str, Any]]:
        """Get all signatures for document."""
        return self._db.fetchall("SELECT * FROM signatures WHERE doc_id = ?  ORDER BY signed_at ASC", (doc_id,))

    # ===== HELPERS =====

    def _row_to_record(self, row: Dict[str, Any]) -> DocumentRecord:
        """Convert DB row to DocumentRecord."""
        status = DocumentStatus[row["status"]]

        return DocumentRecord(
            doc_id=DocumentId(row["doc_id"]),
            title=row["title"],
            doc_type=row["doc_type"],
            status=status,
            version_major=row["version_major"],
            version_minor=row["version_minor"],
            current_file_path=row.get("current_file_path"),
            doc_code=row.get("doc_code"),
            area=row.get("area"),
            process=row.get("process"),
            valid_from=self._parse_dt(row.get("valid_from")),
            next_review=self._parse_dt(row.get("next_review")),
            obsoleted_at=self._parse_dt(row.get("obsoleted_at")),
            created_by=row.get("created_by"),
            created_at=self._parse_dt(row.get("created_at")) or datetime.utcnow(),
            updated_at=self._parse_dt(row.get("updated_at")) or datetime.utcnow(),
            change_note=row.get("change_note"),
            locked_by=row.get("locked_by"),
            locked_at=self._parse_dt(row.get("locked_at")),
            norm_refs=[],
            tags=[]
        )

    @staticmethod
    def _parse_dt(value: Any) -> Optional[datetime]:
        """Parse datetime from DB value."""
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None