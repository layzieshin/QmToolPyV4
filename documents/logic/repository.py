# documents/logic/repository.py
"""
Repository layer for the Documents module, aligned with the domain models.

- Uses your domain types: DocumentID/DocumentId, DocumentRecord, DocumentStatus
- Auto-migrates missing DB columns (version_label, next_review, owner_user_id, comments.version_label)
- Returns DocumentRecord everywhere (no custom _Record type)
- SELECT * to avoid "No item with that key"
- Parses version_label -> version_major / version_minor for DocumentRecord
- set_assignees accepts mapping OR keyword args (authors/reviewers/approvers)
- list_comments lazily extracts from the current file if DB has no comments yet
"""

from __future__ import annotations

import os
import re
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ---- Domain models -----------------------------------------------------------
# be tolerant: DocumentID vs DocumentId; import whichever exists
DomainDocumentId = None
try:
    from documents.models.document_models import DocumentID as DomainDocumentId  # type: ignore
except Exception:
    try:
        from documents.models.document_models import DocumentId as DomainDocumentId  # type: ignore
    except Exception:
        DomainDocumentId = None

try:
    from documents.models.document_models import DocumentRecord, DocumentStatus  # type: ignore
except Exception:
    # Fallbacks (nur zur Not; im Projekt sollten die echten Klassen verfügbar sein)
    from enum import Enum
    from dataclasses import dataclass, field
    class DocumentStatus(Enum):
        DRAFT = "DRAFT"
        IN_REVIEW = "IN_REVIEW"
        APPROVAL = "APPROVAL"
        PUBLISHED = "PUBLISHED"
        ARCHIVED = "ARCHIVED"
        OBSOLETE = "OBSOLETE"
    @dataclass(frozen=True)
    class _DocIdFallback:
        value: str
        def __str__(self) -> str: return self.value
    DomainDocumentId = _DocIdFallback  # type: ignore
    @dataclass
    class DocumentRecord:
        doc_id: Any
        title: str
        doc_type: str
        status: Any
        version_major: int
        version_minor: int
        current_file_path: Optional[str] = None
        doc_code: Optional[str] = None
        area: Optional[str] = None
        process: Optional[str] = None
        valid_from: Optional[datetime] = None
        next_review: Optional[datetime] = None
        obsoleted_at: Optional[datetime] = None
        created_by: Optional[str] = None
        created_at: datetime = datetime.utcnow()
        updated_at: datetime = datetime.utcnow()
        change_note: Optional[str] = None
        norm_refs: List[str] = None
        tags: List[str] = None
        locked_by: Optional[str] = None
        locked_at: Optional[datetime] = None

# ---- Optional DOCX bridge (metadata + comments) ------------------------------
try:
    from documents.logic.wordmeta_bridge import extract_core_and_comments  # type: ignore
except Exception:
    def extract_core_and_comments(path: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        return {}, []

# ============================================================================

@dataclass
class RepoConfig:
    root_path: str
    db_path: str
    id_prefix: str = "DOC"
    id_pattern: str = "{YYYY}-{seq:04d}"
    review_months: int = 24
    watermark_copy: str = "KONTROLLKOPIE"

# ----------------------------------------------------------------------------

def _safe_iso_now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _parse_dt(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except Exception:
        try:
            return datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

def _col(row: sqlite3.Row, name: str, default=None):
    try:
        if hasattr(row, "keys") and name in row.keys():
            return row[name]
    except Exception:
        pass
    return default

def _make_document_id(s: str):
    """
    Construct a domain DocumentID/DocumentId instance from string `s`.
    Supports different class shapes:
      - subclass of str  -> DomainDocumentId(s)
      - dataclass with `value` -> DomainDocumentId(value=s)
      - generic callable -> DomainDocumentId(s)
    """
    if DomainDocumentId is None:
        return s  # worst-case fallback
    try:
        # subclass of str?
        if issubclass(DomainDocumentId, str):  # type: ignore[arg-type]
            inst = DomainDocumentId(s)  # type: ignore[call-arg]
            # try to add .value-like access if missing (non-fatal)
            if not hasattr(inst, "value"):
                # cannot set attribute on immutable str subclass; GUI uses .value—hope domain class has it.
                pass
            return inst
    except Exception:
        pass
    # try value kw
    try:
        return DomainDocumentId(value=s)  # type: ignore[call-arg]
    except Exception:
        pass
    # try positional
    try:
        return DomainDocumentId(s)  # type: ignore[call-arg]
    except Exception:
        return s  # ultimate fallback

# ============================================================================

class DocumentsRepository:
    """
    SQLite repository + filesystem layout.

    <root>/documents_repo/
      <DOC_ID>/active/current.docx|pdf
      <DOC_ID>/versions/v<MAJOR>/
      archived/<DOC_ID>/
    """

    def __init__(self, cfg: RepoConfig) -> None:
        self._cfg = RepoConfig(
            root_path=os.path.abspath(cfg.root_path),
            db_path=os.path.abspath(cfg.db_path),
            id_prefix=cfg.id_prefix,
            id_pattern=cfg.id_pattern,
            review_months=cfg.review_months,
            watermark_copy=cfg.watermark_copy,
        )
        os.makedirs(os.path.dirname(self._cfg.db_path), exist_ok=True)
        os.makedirs(self._root_repo(), exist_ok=True)

        self._conn = sqlite3.connect(self._cfg.db_path)
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    # ------------------------------- paths
    def _root_repo(self) -> str:
        root = self._cfg.root_path
        last = os.path.basename(root.rstrip(os.sep)).lower()
        return root if last == "documents_repo" else os.path.join(root, "documents_repo")

    def _doc_dir(self, doc_id: str) -> str:
        d = os.path.join(self._root_repo(), doc_id)
        os.makedirs(d, exist_ok=True)
        return d

    def _archived_dir(self) -> str:
        d = os.path.join(self._root_repo(), "archived")
        os.makedirs(d, exist_ok=True)
        return d

    def _active_dir(self, doc_id: str) -> str:
        d = os.path.join(self._doc_dir(doc_id), "active")
        os.makedirs(d, exist_ok=True)
        return d

    def _version_dir(self, doc_id: str, version_label: str) -> str:
        try:
            major = str(version_label).split(".", 1)[0]
        except Exception:
            major = "1"
        d = os.path.join(self._doc_dir(doc_id), "versions", f"v{major}")
        os.makedirs(d, exist_ok=True)
        return d

    # ------------------------------- schema / migrations
    def _ensure_schema(self) -> None:
        c = self._conn.cursor()

        c.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id TEXT PRIMARY KEY,
            title TEXT,
            doc_type TEXT,
            status TEXT,
            version_label TEXT,
            current_file_path TEXT,
            created_at TEXT,
            updated_at TEXT,
            next_review TEXT,
            owner_user_id TEXT
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS assignees (
            doc_id TEXT,
            role TEXT,
            user_id TEXT
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            doc_id TEXT,
            author TEXT,
            date TEXT,
            text TEXT,
            version_label TEXT
        )""")
        c.execute("""
        CREATE TABLE IF NOT EXISTS signatures (
            doc_id TEXT,
            step TEXT,
            user_id TEXT,
            signed_at TEXT
        )""")

        def _ensure_column(table: str, col: str, ddl: str, post_sql: Optional[str] = None):
            cols = {r["name"] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}
            if col not in cols:
                try:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
                except Exception:
                    pass
                if post_sql:
                    try:
                        c.execute(post_sql)
                    except Exception:
                        pass

        _ensure_column("documents", "version_label", "TEXT",
                       "UPDATE documents SET version_label='1.0' WHERE version_label IS NULL OR version_label=''")
        _ensure_column("documents", "next_review", "TEXT", None)
        _ensure_column("documents", "owner_user_id", "TEXT", None)
        _ensure_column("comments", "version_label", "TEXT", None)

        c.execute("CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_documents_updated ON documents(updated_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_comments_doc ON comments(doc_id)")

        self._conn.commit()

    # ------------------------------- mapping
    def _row_to_record(self, row: sqlite3.Row) -> DocumentRecord:
        doc_id = _make_document_id(str(_col(row, "doc_id", "")))
        title = _col(row, "title", "") or ""
        doc_type = _col(row, "doc_type", "") or ""
        raw_status = str(_col(row, "status", "DRAFT"))
        try:
            status = DocumentStatus[raw_status]
        except Exception:
            try:
                status = DocumentStatus(raw_status)
            except Exception:
                # manche Enums liefern .value, daher fallback:
                try:
                    status = DocumentStatus[str(raw_status)]
                except Exception:
                    status = getattr(DocumentStatus, "DRAFT")

        ver_label = str(_col(row, "version_label", "1.0"))
        try:
            major_str, minor_str = ver_label.split(".", 1)
            version_major = int(major_str)
            version_minor = int(minor_str)
        except Exception:
            version_major, version_minor = 1, 0

        # nur die Felder setzen, die euer DocumentRecord sicher hat
        # (Dataclass-Feldnamen sind stabil in eurem Modell)
        rec = DocumentRecord(
            doc_id=doc_id,
            title=title,
            doc_type=doc_type,
            status=status,
            version_major=version_major,
            version_minor=version_minor,
            current_file_path=_col(row, "current_file_path", None),
            next_review=_parse_dt(_col(row, "next_review")),
            created_by=_col(row, "owner_user_id"),
            created_at=_parse_dt(_col(row, "created_at")) or datetime.utcnow(),
            updated_at=_parse_dt(_col(row, "updated_at")) or datetime.utcnow(),
            # optionals, falls in eurer Dataclass vorhanden – Python ignoriert fehlende kwargs nicht,
            # daher nur die oben sicheren Felder setzen.
        )
        return rec

    # ------------------------------- queries
    def list(self, status: Optional[DocumentStatus], text: Optional[str], active_only: bool = False) -> List[DocumentRecord]:
        q = "SELECT * FROM documents"
        args: List[Any] = []
        where: List[str] = []
        if status:
            where.append("status=?")
            args.append(status.name if hasattr(status, "name") else str(status))
        if text:
            where.append("(title LIKE ? OR doc_id LIKE ?)")
            args.extend([f"%{text}%", f"%{text}%"])
        if active_only:
            where.append("status IN (?,?,?)")
            args.extend(["DRAFT", "IN_REVIEW", "APPROVAL"])
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY updated_at DESC"

        rows = self._conn.execute(q, args).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get(self, doc_id: str) -> Optional[DocumentRecord]:
        row = self._conn.execute("SELECT * FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
        return self._row_to_record(row) if row else None

    # ------------------------------- comments  (with lazy extraction)
    def list_comments(self, doc_id: str) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT author, date, text, version_label FROM comments WHERE doc_id=? ORDER BY date ASC",
            (doc_id,)
        ).fetchall()
        if not rows:
            # Lazy import for legacy entries (once)
            rec = self.get(doc_id)
            path = getattr(rec, "current_file_path", None) if rec else None
            if path and os.path.isfile(path):
                try:
                    _meta, found = extract_core_and_comments(path)  # type: ignore
                    if found:
                        batch = []
                        for c in found:
                            batch.append((
                                doc_id,
                                str(c.get("author") or ""),
                                str(c.get("date") or ""),
                                str(c.get("text") or ""),
                                str(c.get("version_label") or f"{rec.version_major}.{rec.version_minor}" if rec else "1.0"),
                            ))
                        self._conn.executemany(
                            "INSERT INTO comments(doc_id,author,date,text,version_label) VALUES(?,?,?,?,?)",
                            batch
                        )
                        self._conn.commit()
                        rows = self._conn.execute(
                            "SELECT author, date, text, version_label FROM comments WHERE doc_id=? ORDER BY date ASC",
                            (doc_id,)
                        ).fetchall()
                except Exception:
                    pass

        out: List[Dict[str, Any]] = []
        for r in rows or []:
            out.append({
                "author": _col(r, "author", ""),
                "date": _col(r, "date", ""),
                "text": _col(r, "text", ""),
                "version_label": _col(r, "version_label", None),
            })
        return out

    # ------------------------------- mutations
    def create_from_file(self,
                         title: Optional[str],
                         doc_type: str,
                         user_id: Optional[str],
                         src_file: str) -> DocumentRecord:
        if not src_file or not os.path.isfile(src_file):
            raise FileNotFoundError(f"Source file not found: {src_file}")

        now = _safe_iso_now()
        doc_id = self._new_doc_id()
        ver = "1.0"
        ext = os.path.splitext(src_file)[1].lower().lstrip(".") or "docx"
        active_dir = self._active_dir(doc_id)
        active_path = os.path.join(active_dir, f"current.{ext}")
        shutil.copy2(src_file, active_path)

        # default next_review
        try:
            next_review_dt = datetime.now() + timedelta(days=30 * int(self._cfg.review_months))
            next_review = next_review_dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            next_review = None

        self._conn.execute("""
            INSERT INTO documents(doc_id,title,doc_type,status,version_label,current_file_path,created_at,updated_at,next_review,owner_user_id)
            VALUES(?,?,?,?,?,?,?,?,?,?)
        """, (
            doc_id,
            title or os.path.splitext(os.path.basename(src_file))[0],
            doc_type,
            "DRAFT",
            ver,
            active_path,
            now,
            now,
            next_review,
            user_id or None
        ))
        self._conn.commit()

        # Extract metadata + comments (best effort)
        try:
            meta, comments = extract_core_and_comments(active_path)  # type: ignore
            if comments:
                rows = []
                for c in comments:
                    rows.append((
                        doc_id,
                        str(c.get("author") or ""),
                        str(c.get("date") or ""),
                        str(c.get("text") or ""),
                        str(c.get("version_label") or ver)
                    ))
                self._conn.executemany(
                    "INSERT INTO comments(doc_id,author,date,text,version_label) VALUES(?,?,?,?,?)", rows
                )
                self._conn.commit()
        except Exception:
            pass

        rec = self.get(doc_id)
        if not rec:
            # Shouldn't happen; small fallback
            row = self._conn.execute("SELECT * FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
            return self._row_to_record(row) if row else DocumentRecord(
                doc_id=_make_document_id(doc_id),
                title=title or "",
                doc_type=doc_type,
                status=getattr(DocumentStatus, "DRAFT"),
                version_major=1,
                version_minor=0
            )
        return rec

    def update_metadata(self, data: Dict[str, Any], user_id: Optional[str]) -> None:
        """
        Accepts: doc_id (required), and optionally: title, doc_type, version_label, next_review
        """
        doc_id = str(data.get("doc_id") or "").strip()
        if not doc_id:
            raise ValueError("update_metadata: 'doc_id' missing")

        fields, args = [], []
        for k in ("title", "doc_type", "version_label", "next_review"):
            if k in data and data[k] is not None:
                fields.append(f"{k}=?"); args.append(data[k])
        if not fields:
            return
        fields.append("updated_at=?"); args.append(_safe_iso_now())
        args.append(doc_id)

        self._conn.execute(f"UPDATE documents SET {', '.join(fields)} WHERE doc_id=?", args)
        self._conn.commit()

    def copy_to_destination(self, doc_id: str, dest_dir: str) -> Optional[str]:
        rec = self.get(doc_id)
        if not rec or not rec.current_file_path or not os.path.isfile(rec.current_file_path):
            return None
        os.makedirs(dest_dir, exist_ok=True)
        base = os.path.basename(rec.current_file_path)
        out = os.path.join(dest_dir, f"{doc_id}__{self._cfg.watermark_copy}_{base}")
        shutil.copy2(rec.current_file_path, out)
        return out

    def update_status(self, doc_id: str, new_status: DocumentStatus) -> None:
        self._conn.execute(
            "UPDATE documents SET status=?, updated_at=? WHERE doc_id=?",
            ((new_status.name if hasattr(new_status, "name") else str(new_status)), _safe_iso_now(), doc_id)
        )
        self._conn.commit()

    # ------------------------------- assignees
    def set_assignees(
        self,
        doc_id: str,
        mapping: Optional[Dict[str, Iterable[str]]] = None,
        *,
        authors: Optional[Iterable[str]] = None,
        reviewers: Optional[Iterable[str]] = None,
        approvers: Optional[Iterable[str]] = None,
    ) -> None:
        """
        Accepts either:
          - mapping={"AUTHOR":[...], "REVIEWER":[...], "APPROVER":[...]}
        OR
          - keyword-args: authors=..., reviewers=..., approvers=...
        """
        if mapping is None:
            mapping = {
                "AUTHOR": list(authors or []),
                "REVIEWER": list(reviewers or []),
                "APPROVER": list(approvers or []),
            }
        cur = self._conn.cursor()
        cur.execute("DELETE FROM assignees WHERE doc_id=?", (doc_id,))
        rows = []
        for role, users in (mapping or {}).items():
            for uid in (users or []):
                rows.append((doc_id, str(role), str(uid)))
        if rows:
            cur.executemany("INSERT INTO assignees(doc_id, role, user_id) VALUES(?,?,?)", rows)
        self._conn.commit()

    def get_assignees(self, doc_id: str) -> Dict[str, List[str]]:
        rows = self._conn.execute("SELECT role, user_id FROM assignees WHERE doc_id=?", (doc_id,)).fetchall()
        out: Dict[str, List[str]] = {}
        for r in rows:
            role = _col(r, "role", "")
            uid = _col(r, "user_id", "")
            if role not in out:
                out[role] = []
            if uid:
                out[role].append(uid)
        return out

    # ------------------------------- helpers
    def _new_doc_id(self) -> str:
        year = datetime.now().year
        prefix = self._cfg.id_prefix.strip()
        pattern = self._cfg.id_pattern

        like = f"{prefix}-{year}-%"
        rows = self._conn.execute(
            "SELECT doc_id FROM documents WHERE doc_id LIKE ? ORDER BY doc_id DESC LIMIT 1",
            (like,)
        ).fetchall()
        seq = 0
        if rows:
            last = rows[0]["doc_id"]
            m = re.search(rf"^{re.escape(prefix)}-{year}-(\d+)$", last)
            if m:
                seq = int(m.group(1))
        seq += 1

        doc_id = f"{prefix}-" + pattern.format(YYYY=year, seq=seq)
        while self._conn.execute("SELECT 1 FROM documents WHERE doc_id=?", (doc_id,)).fetchone():
            seq += 1
            doc_id = f"{prefix}-" + pattern.format(YYYY=year, seq=seq)
        return doc_id
