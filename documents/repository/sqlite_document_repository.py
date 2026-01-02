"""SQLite implementation of DocumentRepository.

Uses DatabaseAdapter and StorageAdapter for decoupling.
"""

from __future__ import annotations

import glob
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
import os

from documents.repository.repo_config import RepoConfig
from documents. repository.document_repository import DocumentRepository
from documents.models. document_models import DocumentRecord, DocumentStatus, DocumentId
from documents.dto.assignments import Assignments

# Adapters (NEW!)
from documents.adapters.database_adapter import DatabaseAdapter
from documents.adapters.sqlite_adapter import SQLiteAdapter
from documents.adapters.storage_adapter import StorageAdapter
from documents. adapters.filesystem_storage_adapter import FilesystemStorageAdapter

# Utilities
from documents.logic.id_generator import IdGenerator
from documents.logic. doc_convert import convert_to_pdf
from documents.logic.pdf_tools import make_controlled_copy
from documents.logic.word_tools import extract_core_and_comments



class SQLiteDocumentRepository:
    """
    SQLite-based document repository.

    Uses dependency injection for database and storage adapters.
    """

    def __init__(
        self,
        config: RepoConfig,
        *,
        db_adapter: Optional[DatabaseAdapter] = None,
        storage_adapter: Optional[StorageAdapter] = None
    ):
        """
        Initialize repository.

        Args:
            config: Repository configuration
            db_adapter: Database adapter (default: SQLiteAdapter)
            storage_adapter: Storage adapter (default: FilesystemStorageAdapter)
        """
        self._cfg = config

        # Use provided adapters or create defaults
        self._db = db_adapter or SQLiteAdapter(config.db_path)
        self._storage = storage_adapter or FilesystemStorageAdapter(config. root_path)

        # Initialize schema and ID generator
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
            
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                comment_text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
            );
            
            CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
            CREATE INDEX IF NOT EXISTS idx_documents_updated ON documents(updated_at DESC);
        """)

    # ===== QUERY OPERATIONS =====

    def list(
        self,
        *,
        status: Optional[DocumentStatus] = None,
        text:  Optional[str] = None,
        active_only: bool = False
    ) -> List[DocumentRecord]:
        """List documents with optional filters."""
        query = "SELECT * FROM documents WHERE 1=1"
        params:  List[Any] = []

        if status:
            query += " AND status = ?"
            params.append(status.name)

        if text:
            query += " AND (doc_id LIKE ? OR title LIKE ? )"
            search = f"%{text}%"
            params.extend([search, search])

        if active_only:
            query += """ AND doc_id IN (
                SELECT doc_id FROM workflow_state WHERE workflow_active = 1
            )"""

        query += " ORDER BY updated_at DESC"

        rows = self._db.fetchall(query, tuple(params))
        return [self._dict_to_record(row) for row in rows]

    def get(self, doc_id: str) -> Optional[DocumentRecord]:
        """Get single document by ID."""
        row = self._db.fetchone("SELECT * FROM documents WHERE doc_id = ?", (doc_id,))
        return self._dict_to_record(row) if row else None

    # ===== CREATE OPERATIONS =====

    def create_from_file(
        self,
        *,
        title: Optional[str],
        doc_type: str,
        user_id: str,
        src_file:  str
    ) -> DocumentRecord:
        """Create new document from file."""
        # Generate ID
        doc_id = self._id_gen.next_id()

        # Extract title from filename if not provided
        if not title:
            filename = os.path.basename(src_file)
            title = os.path.splitext(filename)[0]

        # Extract doc_code
        filename_base = os.path.splitext(os.path.basename(src_file))[0]
        doc_code = filename_base. split("_")[0] if "_" in filename_base else None

        # Save file via storage adapter
        dest_path = self._storage.save_working_copy(
            doc_id=doc_id,
            source_path=src_file,
            version="1.0"
        )

        # Insert database record
        now = datetime.utcnow().isoformat(timespec="seconds")
        next_review = (datetime.utcnow() + timedelta(days=30 * self._cfg.review_months)).isoformat(timespec="seconds")

        self._db.insert("documents", {
            "doc_id": doc_id,
            "title": title,
            "doc_type": doc_type,
            "status": DocumentStatus.DRAFT.name,
            "version_major": 1,
            "version_minor":  0,
            "current_file_path": dest_path,
            "doc_code": doc_code,
            "created_by": user_id,
            "created_at": now,
            "updated_at": now,
            "next_review": next_review
        })

        # Initialize workflow state
        self._db. insert("workflow_state", {
            "doc_id": doc_id,
            "workflow_active":  0
        })

        return self. get(doc_id)  # type: ignore

    # ...  (rest of methods use self._db and self._storage)

    def _dict_to_record(self, data: Dict[str, Any]) -> DocumentRecord:
        """Convert dictionary to DocumentRecord."""
        # Parse status
        status = DocumentStatus[data["status"]]

        # Parse dates
        created_at = self._parse_datetime(data. get("created_at"))
        updated_at = self._parse_datetime(data.get("updated_at"))

        return DocumentRecord(
            doc_id=DocumentId(data["doc_id"]),
            title=data["title"],
            doc_type=data["doc_type"],
            status=status,
            version_major=data["version_major"],
            version_minor=data["version_minor"],
            current_file_path=data. get("current_file_path"),
            doc_code=data. get("doc_code"),
            created_by=data. get("created_by"),
            created_at=created_at or datetime.utcnow(),
            updated_at=updated_at or datetime.utcnow()
        )

    def _find_docx_for_record(self, rec: DocumentRecord) -> Optional[str]:
        """Find DOCX file for record."""
        # Try current_file_path first
        if rec.current_file_path and rec.current_file_path.lower().endswith(".docx"):
            if os.path.isfile(rec.current_file_path):
                return rec.current_file_path

        # Search in document directory
        doc_dir = self._storage.get_document_directory(rec.doc_id.value)
        version = f"{rec.version_major}.{rec.version_minor}"
        version_dir = os.path.join(doc_dir, version)

        if os.path.isdir(version_dir):
            candidates = glob.glob(os.path.join(version_dir, "*.docx"))
            if candidates:
                # Sort by modification time, newest first
                candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                return candidates[0]

        return None

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        """Parse datetime from string."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None

    # ===== COMMENTS =====

    def list_comments(self, doc_id: str) -> List[Dict[str, Any]]:
        """Get all comments for document."""
        # Get DB comments
        db_rows = self._db.fetchall("""
            SELECT user_id, comment_text, created_at
            FROM comments
            WHERE doc_id = ?  
            ORDER BY created_at ASC
        """, (doc_id,))

        comments: List[Dict[str, Any]] = []

        for row in db_rows:
            comments.append({
                "author": row.get("user_id", ""),
                "text": row.get("comment_text", ""),
                "date": row.get("created_at", "")
            })

        # Get DOCX comments
        rec = self.get(doc_id)
        if rec and rec.current_file_path:
            docx_path = rec.current_file_path

            # Find DOCX if current is PDF
            if not docx_path.lower().endswith(". docx"):
                docx_path = self._find_docx_for_record(rec)

            if docx_path and os.path.isfile(docx_path):
                try:
                    _, docx_comments = extract_core_and_comments(docx_path)
                    for c in docx_comments:
                        comments.append({
                            "author": c.get("author", ""),
                            "text": c.get("text", ""),
                            "date": str(c.get("date", "")) if c.get("date") else ""
                        })
                except Exception:
                    pass

        return comments

    def get_docx_comments_for_version(
            self,
            doc_id: str,
            version_label: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get DOCX comments for specific version."""
        rec = self.get(doc_id)
        if not rec:
            return []

        docx_path = self._find_docx_for_record(rec)
        if not docx_path or not os.path.isfile(docx_path):
            return []

        try:
            _, comments = extract_core_and_comments(docx_path)
            return [
                {
                    "author": c.get("author", ""),
                    "text": c.get("text", ""),
                    "date": str(c.get("date", "")) if c.get("date") else ""
                }
                for c in comments
            ]
        except Exception:
            return []