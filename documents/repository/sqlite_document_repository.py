"""SQLite implementation of DocumentRepository.

Lightweight repository - only CRUD and simple queries.
Business logic is in services layer.
"""

from __future__ import annotations

import logging
import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import inspect
from documents.adapters.sqlite_adapter import SQLiteAdapter
from documents.logic.id_generator import IdGenerator
from documents.models.document_models import DocumentId, DocumentRecord, DocumentStatus
from documents.repository.repo_config import RepoConfig

logger = logging.getLogger(__name__)


class SQLiteDocumentRepository:
    """SQLite backend for documents.

    Note (Option A):
    - Repository is DB-only.
    - Any file storage/copy/move is handled outside of the repository.
    """

    def __init__(self, config: RepoConfig, *, db_adapter: Optional[Any] = None) -> None:
        """
        Args:
            config:  Repository configuration
            db_adapter:  Database adapter (default: SQLiteAdapter)
        """
        self._cfg = config
        self._db = db_adapter or SQLiteAdapter(config.db_path)

        # Cache for column names (populated lazily)
        self._table_columns_cache: Dict[str, Set[str]] = {}

        self._ensure_schema()
        self._id_gen = IdGenerator(self._db, config.id_prefix, config.id_pattern)

    # =========================================================================
    # Schema Management
    # =========================================================================

    def _ensure_schema(self) -> None:
        """Create database schema if not exists.

        IMPORTANT:
            SQLite cannot add CHECK constraints to an existing table via ALTER TABLE.
            If allowed_doc_types are configured, we enforce that an existing 'documents'
            table already contains the expected constraint. Otherwise we fail fast with
            an explicit instruction to delete/recreate the database (non-production scenario).
        """
        allowed = tuple(getattr(self._cfg, "allowed_doc_types", ()) or ())

        # If a documents table exists already and allowed types are configured,
        # ensure it contains a matching CHECK constraint.
        if allowed:
            self._ensure_documents_table_has_type_constraint(allowed)

        doc_type_def = "doc_type TEXT NOT NULL"
        if allowed:
            quoted = ", ".join([f"'{self._escape_sql_literal(v)}'" for v in allowed])
            doc_type_def += f" CHECK (doc_type IN ({quoted}))"

        self._db.executescript(
            f"""
            CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                {doc_type_def},
                status TEXT NOT NULL,
                version_major INTEGER NOT NULL,
                version_minor INTEGER NOT NULL,
                current_file_path TEXT,
                doc_code TEXT,
                created_by TEXT,
                created_at TEXT,
                updated_at TEXT,
                next_review TEXT,
                signing_pdf_path TEXT
            );

            CREATE TABLE IF NOT EXISTS workflow_state (
                doc_id TEXT PRIMARY KEY,
                workflow_active INTEGER NOT NULL DEFAULT 0
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

        # Ensure assignments table exists with compatible structure
        self._ensure_assignments_table()

        # Run migrations for existing tables
        self._migrate_workflow_state()
        self._migrate_documents_signing_pdf()

    @staticmethod
    def _escape_sql_literal(value: str) -> str:
        """Escape a value for use in a single-quoted SQL literal."""
        return value.replace("'", "''")

    def _ensure_documents_table_has_type_constraint(self, allowed: tuple[str, ...]) -> None:
        """Fail fast if an existing documents table does not contain the expected CHECK constraint.

        We intentionally do not auto-migrate here. The feature is currently non-production
        and the database can be recreated safely.
        """
        row = self._db.fetchone(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='documents'"
        )
        if not row:
            # Table does not exist yet - will be created with the constraint.
            return

        create_sql = row.get("sql") if isinstance(row, dict) else row[0]
        if not create_sql:
            return

        # Minimal heuristic: constraint exists and includes all allowed values.
        if "CHECK" not in create_sql or "doc_type" not in create_sql:
            raise RuntimeError(
                "Documents DB schema is outdated (missing doc_type CHECK constraint). "
                f"Please delete the database file and restart: {self._cfg.db_path}"
            )

        missing = [
            code for code in allowed
            if f"'{self._escape_sql_literal(code)}'" not in create_sql
        ]
        if missing:
            raise RuntimeError(
                "Documents DB schema is outdated (doc_type CHECK constraint does not match allowed types). "
                f"Missing: {', '.join(missing)}. Please delete the database file and restart: {self._cfg.db_path}"
            )

    def _ensure_assignments_table(self) -> None:
        """Ensure assignments table exists with compatible structure."""
        # Check if table exists
        table_exists = self._db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='assignments'"
        )

        if not table_exists:
            # Create new table with preferred schema
            self._db.executescript(
                """
                CREATE TABLE assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    assigned_at TEXT,
                    UNIQUE(doc_id, role, user_id)
                );
                """
            )
        # Clear cache so columns are re-detected
        self._table_columns_cache.pop("assignments", None)

    def _get_table_columns(self, table_name: str) -> Set[str]:
        """Get column names for a table (cached)."""
        if table_name in self._table_columns_cache:
            return self._table_columns_cache[table_name]

        try:
            rows = self._db.fetchall(f"PRAGMA table_info({table_name})")
            columns = {row["name"] for row in rows} if rows else set()
            self._table_columns_cache[table_name] = columns
            return columns
        except Exception as ex:
            logger.error(f"Failed to get columns for {table_name}: {ex}")
            return set()

    def _get_assignments_user_column(self) -> str:
        """Detect whether assignments table uses 'username' or 'user_id' column."""
        columns = self._get_table_columns("assignments")
        if "user_id" in columns:
            return "user_id"
        elif "username" in columns:
            return "username"
        else:
            # Fallback
            return "user_id"

    def _assignments_has_assigned_at(self) -> bool:
        """Check if assignments table has assigned_at column."""
        columns = self._get_table_columns("assignments")
        return "assigned_at" in columns

    def _migrate_workflow_state(self) -> None:
        """Add started_by column to workflow_state if missing."""
        columns = self._get_table_columns("workflow_state")
        if "started_by" not in columns:
            try:
                self._db.executescript(
                    "ALTER TABLE workflow_state ADD COLUMN started_by TEXT;"
                )
                # Clear cache
                self._table_columns_cache.pop("workflow_state", None)
                logger.info("Migrated workflow_state:  added started_by column")
            except Exception as ex:
                logger.debug(f"workflow_state migration skipped: {ex}")

    def _migrate_documents_signing_pdf(self) -> None:
        """Add signing_pdf_path column to documents if missing.

        This column is the single source of truth for the current signing PDF
        that is passed along the signing chain. It must be cleared on workflow abort.
        """
        columns = self._get_table_columns("documents")
        if "signing_pdf_path" in columns:
            return

        try:
            self._db.executescript(
                "ALTER TABLE documents ADD COLUMN signing_pdf_path TEXT;"
            )
            self._table_columns_cache.pop("documents", None)
            logger.info("Migrated documents: added signing_pdf_path column")
        except Exception as ex:
            # SQLite raises if the column already exists (race) or table is missing.
            logger.debug(f"documents migration skipped: {ex}")

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def create(
        self,
        *,
        title: str,
        doc_type: str,
        user_id: str,
        file_path: str,
        doc_code: Optional[str] = None,
    ) -> DocumentRecord:
        """Create new document record."""
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
                    "workflow_state",
                    {"doc_id": doc_id, "workflow_active": 0},
                )

                rec = self.get(doc_id)
                if rec is None:
                    raise RuntimeError(
                        "Document was inserted but could not be reloaded."
                    )
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
            "Failed to create document after retries due to duplicate doc_id: "
            f"{last_exc}"
        )

    def create_from_file(
        self,
        *,
        title: Optional[str],
        doc_type: str,
        user_id: str,
        src_file: str,
    ) -> DocumentRecord:
        """Create new document record from an existing DOCX file."""
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

    def exists(self, doc_id: str) -> bool:
        """Check if document exists."""
        row = self._db.fetchone("SELECT 1 FROM documents WHERE doc_id=?", (doc_id,))
        return row is not None

    def list(
        self,
        *,
        status: Optional[DocumentStatus] = None,
        text: Optional[str] = None,
        active_only: bool = False,
    ) -> List[DocumentRecord]:
        """List documents with optional filters."""
        # Build query with JOINs for active_only filter
        if active_only:
            sql = """
                SELECT d.*
                FROM documents d
                LEFT JOIN workflow_state w ON d.doc_id = w.doc_id
                WHERE 1=1
            """
        else:
            sql = "SELECT * FROM documents WHERE 1=1"

        params: List[Any] = []

        # Status filter
        if status is not None:
            if active_only:
                sql += " AND d.status = ?"
            else:
                sql += " AND status = ?"
            params.append(status.name)

        # Text search (LIKE on title and doc_code)
        if text and text.strip():
            search_term = f"%{text.strip()}%"
            if active_only:
                sql += " AND (d.title LIKE ? OR d.doc_code LIKE ? OR d.doc_id LIKE ?)"
            else:
                sql += " AND (title LIKE ? OR doc_code LIKE ? OR doc_id LIKE ?)"
            params.extend([search_term, search_term, search_term])

        # Active only filter (via workflow_state)
        if active_only:
            sql += " AND w.workflow_active = 1"

        # Order by updated_at DESC
        if active_only:
            sql += " ORDER BY d.updated_at DESC"
        else:
            sql += " ORDER BY updated_at DESC"

        try:
            rows = self._db.fetchall(sql, tuple(params)) or []
            return [self._row_to_record(r) for r in rows]
        except Exception as ex:
            logger.error(f"Error in list(): {ex}")
            return []

    # =========================================================================
    # Metadata Update
    # =========================================================================

    def update_metadata(self, data: Dict[str, Any], user_id: str) -> None:
        """Update document metadata."""
        doc_id = data.get("doc_id")
        if not doc_id:
            raise ValueError("data must include 'doc_id'")

        if not self.exists(doc_id):
            raise ValueError(f"Document not found: {doc_id}")

        # Collect updateable fields
        allowed_fields = {"title", "doc_type", "doc_code", "next_review"}
        updates: Dict[str, Any] = {}
        for key in allowed_fields:
            if key in data:
                updates[key] = data[key]

        if not updates:
            return

        updates["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [doc_id]

        sql = f"UPDATE documents SET {set_clause} WHERE doc_id = ?"
        self._db.execute(sql, tuple(values))
        self._db.commit()

    # =========================================================================
    # Status Management
    # =========================================================================

    def set_status(
        self,
        doc_id: str,
        status: DocumentStatus,
        user_id: str,
        reason: Optional[str] = None,
    ) -> None:
        """Change document status."""
        if not self.exists(doc_id):
            raise ValueError(f"Document not found: {doc_id}")

        now = datetime.utcnow().isoformat(timespec="seconds")

        self._db.execute(
            "UPDATE documents SET status = ?, updated_at = ? WHERE doc_id = ?",
            (status.name, now, doc_id),
        )
        self._db.commit()

    # =========================================================================
    # Version Management
    # =========================================================================

    def bump_minor_version(
        self,
        doc_id: str,
        user_id: str,
        reason: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        """Increment minor version (e.g., 1.0 → 1.1)."""
        rec = self.get(doc_id)
        if not rec:
            return False, f"Document not found: {doc_id}"

        new_minor = rec.version_minor + 1
        now = datetime.utcnow().isoformat(timespec="seconds")

        self._db.execute(
            "UPDATE documents SET version_minor = ?, updated_at = ? WHERE doc_id = ? ",
            (new_minor, now, doc_id),
        )
        self._db.commit()
        return True, None

    def bump_major_version(
        self,
        doc_id: str,
        user_id: str,
        reason: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        """Increment major version (e.g., 1.5 → 2.0)."""
        rec = self.get(doc_id)
        if not rec:
            return False, f"Document not found: {doc_id}"

        new_major = rec.version_major + 1
        now = datetime.utcnow().isoformat(timespec="seconds")

        self._db.execute(
            "UPDATE documents SET version_major = ?, version_minor = 0, updated_at = ? WHERE doc_id = ?",
            (new_major, now, doc_id),
        )
        self._db.commit()
        return True, None

    # =========================================================================
    # Workflow State
    # =========================================================================

    def is_workflow_active(self, doc_id: str) -> bool:
        """Check if workflow is active for document."""
        try:
            row = self._db.fetchone(
                "SELECT workflow_active FROM workflow_state WHERE doc_id = ?",
                (doc_id,),
            )
            if not row:
                return False
            return bool(row.get("workflow_active", 0))
        except Exception as ex:
            logger.error(f"Error checking workflow_active: {ex}")
            return False

    def set_workflow_active(
        self,
        doc_id: str,
        active: bool,
        started_by: Optional[str] = None,
    ) -> None:
        """Set workflow active state."""
        existing = self._db.fetchone(
            "SELECT 1 FROM workflow_state WHERE doc_id = ?", (doc_id,)
        )

        has_started_by = "started_by" in self._get_table_columns("workflow_state")

        if not existing:
            data = {"doc_id": doc_id, "workflow_active": 1 if active else 0}
            if has_started_by:
                data["started_by"] = started_by
            self._db.insert("workflow_state", data)
        else:
            if active and has_started_by:
                self._db.execute(
                    "UPDATE workflow_state SET workflow_active = 1, started_by = ?  WHERE doc_id = ?",
                    (started_by, doc_id),
                )
            elif active:
                self._db.execute(
                    "UPDATE workflow_state SET workflow_active = 1 WHERE doc_id = ?",
                    (doc_id,),
                )
            else:
                self._db.execute(
                    "UPDATE workflow_state SET workflow_active = 0 WHERE doc_id = ?",
                    (doc_id,),
                )
            self._db.commit()

    def get_workflow_starter(self, doc_id: str) -> Optional[str]:
        """Get user ID who started the workflow."""
        has_started_by = "started_by" in self._get_table_columns("workflow_state")
        if not has_started_by:
            return None

        try:
            row = self._db.fetchone(
                "SELECT started_by FROM workflow_state WHERE doc_id = ?",
                (doc_id,),
            )
            if not row:
                return None
            return row.get("started_by")
        except Exception as ex:
            logger.debug(f"Error getting workflow_starter: {ex}")
            return None

    # =========================================================================
    # Assignments
    # =========================================================================

    def get_assignees(self, doc_id: str) -> Dict[str, List[str]]:
        """Get role assignments."""
        result: Dict[str, List[str]] = {
            "AUTHOR": [],
            "REVIEWER": [],
            "APPROVER": [],
        }

        user_col = self._get_assignments_user_column()
        has_assigned_at = self._assignments_has_assigned_at()

        try:
            # Build query based on available columns
            if has_assigned_at:
                sql = (
                    f"SELECT role, {user_col} FROM assignments WHERE doc_id = ?  ORDER BY assigned_at"
                )
            else:
                sql = f"SELECT role, {user_col} FROM assignments WHERE doc_id = ?"

            rows = self._db.fetchall(sql, (doc_id,))

            for row in rows or []:
                role = (row.get("role") or "").upper()
                user_value = row.get(user_col) or ""
                if role in result and user_value:
                    result[role].append(user_value)

        except Exception as ex:
            logger.error(f"Error getting assignees: {ex}")

        return result

    def set_assignees(self, doc_id: str, mapping: Dict[str, List[str]]) -> None:
        """Set role assignments."""
        user_col = self._get_assignments_user_column()
        has_assigned_at = self._assignments_has_assigned_at()
        now = datetime.utcnow().isoformat(timespec="seconds")

        try:
            # Clear existing assignments for this document
            self._db.execute("DELETE FROM assignments WHERE doc_id = ?", (doc_id,))

            # Insert new assignments
            for role, usernames in mapping.items():
                role_upper = role.upper()
                for username in usernames:
                    if username and username.strip():
                        data = {
                            "doc_id": doc_id,
                            "role": role_upper,
                            user_col: username.strip(),
                        }
                        if has_assigned_at:
                            data["assigned_at"] = now
                        self._db.insert("assignments", data)
        except Exception as ex:
            logger.error(f"Error setting assignees: {ex}")
            raise

    def get_owner(self, doc_id: str) -> Optional[str]:
        """Get document owner user ID (created_by)."""
        try:
            row = self._db.fetchone(
                "SELECT created_by FROM documents WHERE doc_id = ?",
                (doc_id,),
            )
            if not row:
                return None
            return row.get("created_by")
        except Exception as ex:
            logger.error(f"Error getting owner: {ex}")
            return None

    # =========================================================================
    # Comments
    # =========================================================================

    def list_comments(self, doc_id: str) -> List[Dict[str, Any]]:
        """Return extracted DOCX comments for the current document file."""
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
            from word_meta.logic.docx_comments_reader import read_docx_comments
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

    def get_docx_comments_for_version(
        self, doc_id: str, version_label: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get DOCX comments for specific version."""
        return self.list_comments(doc_id)

    # =========================================================================
    # PDF Operations (Stubs)
    # =========================================================================

    def generate_review_pdf(self, doc_id: str) -> Optional[str]:
        """Generate PDF for review."""
        return None

    # =========================================================================
    # Signing PDF (Single Source of Truth)
    # =========================================================================

    def get_signing_pdf(self, doc_id: str) -> Optional[str]:
        """Return the current signing PDF path for the document, if any."""
        try:
            row = self._db.fetchone(
                "SELECT signing_pdf_path FROM documents WHERE doc_id=?",
                (doc_id,),
            )
            if not row:
                return None
            return row.get("signing_pdf_path")
        except Exception as ex:
            logger.error(f"Error getting signing_pdf_path: {ex}")
            return None

    def set_signing_pdf(self, doc_id: str, pdf_path: str) -> None:
        """Persist the current signing PDF path for the document."""
        if not self.exists(doc_id):
            raise ValueError(f"Document not found: {doc_id}")

        try:
            self._db.execute(
                "UPDATE documents SET signing_pdf_path = ? WHERE doc_id = ?",
                (pdf_path, doc_id),
            )
            self._db.commit()
        except Exception as ex:
            logger.error(f"Error setting signing_pdf_path: {ex}")
            raise

    def clear_signing_pdf(self, doc_id: str) -> None:
        """Clear signing PDF reference for the document (e.g. on workflow abort)."""
        if not self.exists(doc_id):
            return

        try:
            self._db.execute(
                "UPDATE documents SET signing_pdf_path = NULL WHERE doc_id = ?",
                (doc_id,),
            )
            self._db.commit()
        except Exception as ex:
            logger.error(f"Error clearing signing_pdf_path: {ex}")
            raise

    
    def list_signatures(self, doc_id: str) -> List[Dict[str, Any]]:
        """Return signature rows for the given document."""
        if not doc_id:
            return []
        try:
            rows = self._db.query(
                "SELECT doc_id, role, username, signed_at, comment FROM signatures WHERE doc_id = ? ORDER BY signed_at ASC",
                (doc_id,),
            )
            # Ensure list of dicts
            return [dict(r) for r in (rows or [])]
        except Exception as ex:
            logger.error(f"Error listing signatures for {doc_id}: {ex}")
            return []


    def attach_signed_pdf(self, doc_id: str, signed_pdf_path: str, step: str, user_id: str,
                          reason: Optional[str] = None, ) -> tuple[bool, Optional[str]]:
        """Attach signed PDF to document."""
        if not self.exists(doc_id):
            return False, f"Document not found: {doc_id}"
        now = datetime.utcnow().isoformat(timespec="seconds")
        try:
            self._db.insert(
                "signatures",
                {
                "doc_id": doc_id,
                "role": step,
                "username": user_id,
                "signed_at": now,
                "comment": reason,
                },
            )
            return True, None
        except Exception as ex: (
            logger.error(f"Error attaching signed PDF: {ex}"),)

        return False,(str(ex))


    def export_pdf_with_version_suffix(self, doc_id: str) -> Optional[str]:
        """Export PDF with version number in filename."""
        return None

    def copy_to_destination(
        self,
        doc_id: str,
        dest_dir: str,
    ) -> Optional[str]:
        """Copy controlled document to destination.

        Robust Windows implementation:
        - Validates dest_dir strictly (must be an existing directory or creatable).
        - Retries on Windows sharing violations / transient errors.
        - Does NOT use mkstemp(dir=dest_dir) and does NOT use os.replace()
          (both can trigger WinError 87 depending on path quirks).
        """
        rec = self.get(doc_id)
        if not rec:
            return None

        # Prefer signing PDF if available (single source of truth), else fallback.
        src_path = None
        try:
            signing_pdf = self.get_signing_pdf(doc_id)
        except Exception:
            signing_pdf = None

        if signing_pdf and os.path.isfile(signing_pdf):
            src_path = signing_pdf
        else:
            src_path = rec.current_file_path

        if not src_path or not os.path.isfile(src_path):
            return None

        if not isinstance(dest_dir, str) or not dest_dir.strip():
            logger.error("copy_to_destination: dest_dir is empty or not a string")
            return None

        dest_dir = os.path.expandvars(os.path.expanduser(dest_dir.strip()))

        # dest_dir MUST be a directory (askdirectory should provide that, but we enforce it)
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except Exception as ex:
            logger.error(f"copy_to_destination: invalid dest_dir={dest_dir!r}: {ex}")
            return None

        if not os.path.isdir(dest_dir):
            logger.error(f"copy_to_destination: dest_dir is not a directory: {dest_dir!r}")
            return None

        # Build destination filename (keep base name)
        base = os.path.basename(src_path)
        dst_path = os.path.join(dest_dir, base)

        # If file exists, add suffix _copyN
        if os.path.exists(dst_path):
            name, ext = os.path.splitext(base)
            n = 1
            while True:
                cand = os.path.join(dest_dir, f"{name}_copy{n}{ext}")
                if not os.path.exists(cand):
                    dst_path = cand
                    break
                n += 1

        # Copy with retries
        retries = 5
        for attempt in range(1, retries + 1):
            try:
                shutil.copy2(src_path, dst_path)
                return dst_path
            except Exception as ex:
                if attempt >= retries:
                    logger.error(f"copy_to_destination failed after retries: {ex}")
                    return None
                try:
                    import time
                    time.sleep(0.2 * attempt)
                except Exception:
                    pass

        return None

    # =========================================================================
    # Internal Helpers: Row mapping
    # =========================================================================

    def _row_to_record(self, row: Dict[str, Any]) -> DocumentRecord:
        """Map DB row to DocumentRecord in a backward-compatible way.

        The DocumentRecord constructor may differ between iterations (models vs dto).
        We therefore only pass kwargs that are actually accepted by the constructor.
        """
        doc_id_val = row.get("doc_id") or ""

        # DocumentId wrapper may differ by iteration
        try:
            doc_id = DocumentId(doc_id_val)  # type: ignore[misc]
        except Exception:
            doc_id = doc_id_val  # type: ignore[assignment]

        status_txt = row.get("status") or getattr(DocumentStatus, "DRAFT", None).name  # type: ignore[union-attr]
        try:
            status = DocumentStatus[status_txt]  # type: ignore[index]
        except Exception:
            try:
                status = DocumentStatus.DRAFT  # type: ignore[attr-defined]
            except Exception:
                status = status_txt  # type: ignore[assignment]

        # Base kwargs we want to provide (newer schema may include signing_pdf_path)
        kwargs = {
            "doc_id": doc_id,
            "title": row.get("title") or "",
            "doc_type": row.get("doc_type") or "",
            "status": status,
            "version_major": int(row.get("version_major") or 1),
            "version_minor": int(row.get("version_minor") or 0),
            "current_file_path": row.get("current_file_path") or None,
            "doc_code": row.get("doc_code") or None,
            "created_by": row.get("created_by") or None,
            "created_at": row.get("created_at") or None,
            "updated_at": row.get("updated_at") or None,
            "next_review": row.get("next_review") or None,
            "signing_pdf_path": row.get("signing_pdf_path") or None,
        }

        # Filter kwargs to what the constructor accepts
        try:
            sig = inspect.signature(DocumentRecord)  # type: ignore[arg-type]
            allowed = set(sig.parameters.keys())
            kwargs = {k: v for k, v in kwargs.items() if k in allowed}
        except Exception:
            # If inspection fails, fall back: drop the newest field first
            kwargs.pop("signing_pdf_path", None)
        return DocumentRecord(**kwargs)