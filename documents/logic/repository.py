# documents/logic/repository.py
from __future__ import annotations

import os
import re
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple
from pathlib import Path

from documents.models.document_models import DocumentId, DocumentRecord, DocumentStatus  # type: ignore
from core.common.db_interface import SQLiteRepository

# --- Optional DOCX metadata/comments bridge -----------------------------------
try:
    from documents.logic.wordmeta_bridge import extract_core_and_comments  # type: ignore
except Exception:
    def extract_core_and_comments(path: str):
        return {}, []

# ------------------------------------------------------------------------------
@dataclass
class RepoConfig:
    root_path: str
    db_path: str
    id_prefix: str = "DOC"
    id_pattern: str = "{YYYY}-{seq:04d}"
    review_months: int = 24
    watermark_copy: str = "KONTROLLKOPIE"

def _safe_iso_now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _parse_dt(val: Optional[str]) -> Optional[datetime]:
    if not val: return None
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

_CODE_RE = re.compile(r"^[A-Z0-9\-]+$")
def _looks_like_external_code(token: str) -> bool:
    if not token: return False
    t = token.strip().upper()
    if not _CODE_RE.fullmatch(t): return False
    return any(c.isalpha() for c in t) and any(c.isdigit() for c in t) and len(t) >= 5

def _extract_code_from_filename(path: str) -> Optional[str]:
    try:
        base = os.path.splitext(os.path.basename(path))[0]
        candidate = base.split("_", 1)[0].strip().upper()
        return candidate if _looks_like_external_code(candidate) else None
    except Exception:
        return None

def _extract_code_from_docid(doc_id: str) -> Optional[str]:
    return doc_id if _looks_like_external_code(doc_id) else None

# ------------------------------------------------------------------------------
class DocumentsRepository(SQLiteRepository):
    """
    SQLite + Filesystem Repository.

    Neu:
    - `workflow_state` als robuste Persistenz für aktive Workflows (Fallback, falls
      die Spalte `documents.workflow_active` nicht existiert).
    - Alle Abfragen sind schema-tolerant; kein „no such column“ mehr.
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

        super().__init__(Path(self._cfg.db_path))
        self._conn = self.connect()
        self._ensure_schema()

    # ------------------------------ paths
    def _root_repo(self) -> str:
        root = self._cfg.root_path
        last = os.path.basename(root.rstrip(os.sep)).lower()
        return root if last == "documents_repo" else os.path.join(root, "documents_repo")

    def _doc_dir(self, doc_id: str) -> str:
        d = os.path.join(self._root_repo(), doc_id); os.makedirs(d, exist_ok=True); return d

    def _archived_dir(self) -> str:
        d = os.path.join(self._root_repo(), "archived"); os.makedirs(d, exist_ok=True); return d

    def _active_dir(self, doc_id: str) -> str:
        d = os.path.join(self._doc_dir(doc_id), "active"); os.makedirs(d, exist_ok=True); return d

    def _version_dir(self, doc_id: str, version_label: str) -> str:
        try: major = str(version_label).split(".", 1)[0]
        except Exception: major = "1"
        d = os.path.join(self._doc_dir(doc_id), "versions", f"v{major}")
        os.makedirs(d, exist_ok=True); return d

    # ------------------------------ schema & migrations
    def _ensure_schema(self) -> None:
        c = self._conn.cursor()

        c.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id TEXT PRIMARY KEY,
            title TEXT,
            doc_type TEXT,
            status TEXT,
            version_label TEXT,
            version_major INTEGER,
            version_minor INTEGER,
            current_file_path TEXT,
            created_at TEXT,
            updated_at TEXT,
            next_review TEXT,
            owner_user_id TEXT,
            obsoleted_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS assignees (doc_id TEXT, role TEXT, user_id TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS comments (doc_id TEXT, author TEXT, date TEXT, text TEXT, version_label TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS signatures (doc_id TEXT, step TEXT, user_id TEXT, signed_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS status_log (doc_id TEXT, old_status TEXT, new_status TEXT, user_id TEXT, reason TEXT, changed_at TEXT)""")

        # we also support an auxiliary workflow_state table (robust, no ALTER TABLE dependency)
        c.execute("""
        CREATE TABLE IF NOT EXISTS workflow_state (
            doc_id TEXT PRIMARY KEY,
            active INTEGER DEFAULT 0,
            started_by TEXT,
            started_at TEXT
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

        # version fields on documents
        _ensure_column("documents", "version_label", "TEXT",
                       "UPDATE documents SET version_label='1.0' WHERE version_label IS NULL OR version_label=''")
        _ensure_column("documents", "version_major", "INTEGER",
                       "UPDATE documents SET version_major=1 WHERE version_major IS NULL")
        _ensure_column("documents", "version_minor", "INTEGER",
                       "UPDATE documents SET version_minor=0 WHERE version_minor IS NULL")
        _ensure_column("documents", "next_review", "TEXT", None)
        _ensure_column("documents", "owner_user_id", "TEXT", None)
        _ensure_column("documents", "obsoleted_at", "TEXT", None)

        # Optional: falls Spalte bereits existiert, initialisieren
        _ensure_column("documents", "workflow_active", "INTEGER DEFAULT 0",
                       "UPDATE documents SET workflow_active=0 WHERE workflow_active IS NULL")
        _ensure_column("documents", "workflow_started_by", "TEXT", None)
        _ensure_column("documents", "workflow_started_at", "TEXT", None)

        # Indizes – nur anlegen, wenn Spalten existieren
        c.execute("CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_documents_updated ON documents(updated_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_comments_doc ON comments(doc_id)")
        cols = {r["name"] for r in c.execute("PRAGMA table_info(documents)").fetchall()}
        if "workflow_active" in cols:
            c.execute("CREATE INDEX IF NOT EXISTS idx_documents_wf_active ON documents(workflow_active)")

        self._conn.commit()

    # ------------------------------ helpers
    def _known_columns(self, table: str) -> List[str]:
        rows = self._conn.execute(f"PRAGMA table_info({table})").fetchall()
        return [r["name"] for r in rows]

    def _has_column(self, table: str, col: str) -> bool:
        try:
            return col in self._known_columns(table)
        except Exception:
            return False

    # ------------------------------ mapper
    def _row_to_record(self, row: sqlite3.Row) -> DocumentRecord:
        raw_id = str(_col(row, "doc_id", "")); doc_id = DocumentId(value=raw_id)
        title = _col(row, "title", "") or ""; doc_type = _col(row, "doc_type", "") or ""
        raw_status = str(_col(row, "status", "DRAFT"))
        try: status = DocumentStatus[raw_status]
        except Exception:
            try: status = DocumentStatus(raw_status)
            except Exception: status = DocumentStatus.DRAFT

        if ("version_major" in row.keys() and _col(row, "version_major") is not None
            and "version_minor" in row.keys() and _col(row, "version_minor") is not None):
            try:
                version_major = int(_col(row, "version_major")); version_minor = int(_col(row, "version_minor"))
            except Exception:
                version_major, version_minor = 1, 0
        else:
            label = str(_col(row, "version_label", "1.0"))
            try:
                mj_s, mn_s = label.split(".", 1); version_major, version_minor = int(mj_s), int(mn_s)
            except Exception:
                version_major, version_minor = 1, 0

        doc_code = _extract_code_from_docid(raw_id)
        if not doc_code:
            path_for_code = _col(row, "current_file_path", None)
            if path_for_code:
                doc_code = _extract_code_from_filename(path_for_code)

        return DocumentRecord(
            doc_id=doc_id,
            title=title,
            doc_type=doc_type,
            status=status,
            version_major=version_major,
            version_minor=version_minor,
            current_file_path=_col(row, "current_file_path", None),
            doc_code=doc_code,
            next_review=_parse_dt(_col(row, "next_review")),
            created_by=_col(row, "owner_user_id"),
            created_at=_parse_dt(_col(row, "created_at")) or datetime.utcnow(),
            updated_at=_parse_dt(_col(row, "updated_at")) or datetime.utcnow(),
        )

    # ------------------------------ queries
    def list(self, status: Optional[DocumentStatus], text: Optional[str], active_only: bool = False) -> List[DocumentRecord]:
        args: List[Any] = []
        where: List[str] = []

        if status:
            where.append("d.status=?")
            args.append(status.name if hasattr(status, "name") else str(status))
        if text:
            where.append("(d.title LIKE ? OR d.doc_id LIKE ?)")
            args.extend([f"%{text}%", f"%{text}%"])

        # Verfügbarkeit der Spalte prüfen
        has_wf_col = self._has_column("documents", "workflow_active")

        if active_only:
            # Aktiv = IN_REVIEW/APPROVAL/PUBLISHED oder (DRAFT & workflow aktiv)
            if has_wf_col:
                where.append("(d.status IN (?,?,?) OR (d.status=? AND d.workflow_active=1))")
                args.extend(["IN_REVIEW", "APPROVAL", "PUBLISHED", "DRAFT"])
                q = "SELECT d.* FROM documents d"
            else:
                # über workflow_state gehen
                where.append("(d.status IN (?,?,?) OR (d.status=? AND COALESCE(ws.active,0)=1))")
                args.extend(["IN_REVIEW", "APPROVAL", "PUBLISHED", "DRAFT"])
                q = "SELECT d.* FROM documents d LEFT JOIN workflow_state ws ON ws.doc_id=d.doc_id"
        else:
            q = "SELECT d.* FROM documents d"
            # kein JOIN nötig

        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY d.updated_at DESC"

        rows = self._conn.execute(q, args).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get(self, doc_id: str) -> Optional[DocumentRecord]:
        row = self._conn.execute("SELECT * FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
        return self._row_to_record(row) if row else None

    # ------------------------------ comments (lazy import)
    def list_comments(self, doc_id: str) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT author, date, text, version_label FROM comments WHERE doc_id=? ORDER BY date ASC",
            (doc_id,)
        ).fetchall()
        if not rows:
            rec = self.get(doc_id)
            path = getattr(rec, "current_file_path", None) if rec else None
            if path and os.path.isfile(path):
                try:
                    _meta, found = extract_core_and_comments(path)
                    if found:
                        vlabel = f"{rec.version_major}.{rec.version_minor}" if rec else "1.0"
                        batch = [(doc_id, str(c.get("author") or ""), str(c.get("date") or ""), str(c.get("text") or ""), str(c.get("version_label") or vlabel)) for c in found]
                        self._conn.executemany("INSERT INTO comments(doc_id,author,date,text,version_label) VALUES(?,?,?,?,?)", batch)
                        self._conn.commit()
                        rows = self._conn.execute(
                            "SELECT author, date, text, version_label FROM comments WHERE doc_id=? ORDER BY date ASC",
                            (doc_id,)
                        ).fetchall()
                except Exception:
                    pass
        out: List[Dict[str, Any]] = []
        for r in rows or []:
            out.append({"author": _col(r, "author", ""), "date": _col(r, "date", ""), "text": _col(r, "text", ""), "version_label": _col(r, "version_label", None)})
        return out

    # ------------------------------ assignees
    def set_assignees(self, doc_id: str, mapping: Optional[Dict[str, Iterable[str]]] = None, *,
                      authors: Optional[Iterable[str]] = None, reviewers: Optional[Iterable[str]] = None, approvers: Optional[Iterable[str]] = None) -> None:
        if mapping is None:
            mapping = {"AUTHOR": list(authors or []), "REVIEWER": list(reviewers or []), "APPROVER": list(approvers or [])}
        cur = self._conn.cursor()
        cur.execute("DELETE FROM assignees WHERE doc_id=?", (doc_id,))
        rows = []
        for role, users in (mapping or {}).items():
            r = str(role).strip().upper()
            for uid in (users or []):
                u = str(uid).strip()
                if u: rows.append((doc_id, r, u))
        if rows:
            cur.executemany("INSERT INTO assignees(doc_id, role, user_id) VALUES(?,?,?)", rows)
        self._conn.commit()

    def get_assignees(self, doc_id: str) -> Dict[str, List[str]]:
        rows = self._conn.execute("SELECT role, user_id FROM assignees WHERE doc_id=?", (doc_id,)).fetchall()
        out: Dict[str, List[str]] = {}
        for r in rows or []:
            role = str(_col(r, "role", "") or "").strip().upper()
            uid = str(_col(r, "user_id", "") or "").strip()
            if not role: continue
            out.setdefault(role, [])
            if uid: out[role].append(uid)
        return out

    # ------------------------------ create/update
    def create_from_file(self, title: Optional[str], doc_type: str, user_id: Optional[str], src_file: str) -> DocumentRecord:
        if not src_file or not os.path.isfile(src_file):
            raise FileNotFoundError(f"Source file not found: {src_file}")
        now = _safe_iso_now()

        preferred_id = _extract_code_from_filename(src_file)
        use_id = None
        if preferred_id:
            exists = self._conn.execute("SELECT 1 FROM documents WHERE doc_id=?", (preferred_id,)).fetchone()
            if not exists: use_id = preferred_id
        new_id = use_id or self._new_doc_id()

        ver_label = "1.0"; ver_major, ver_minor = 1, 0
        ext = os.path.splitext(src_file)[1].lower().lstrip(".") or "docx"
        active_dir = self._active_dir(new_id)
        active_path = os.path.join(active_dir, f"current.{ext}")
        shutil.copy2(src_file, active_path)

        try:
            next_review_dt = datetime.now() + timedelta(days=30 * int(self._cfg.review_months))
            next_review = next_review_dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            next_review = None

        candidate_values: Dict[str, Any] = {
            "doc_id": new_id,
            "title": title or os.path.splitext(os.path.basename(src_file))[0],
            "doc_type": doc_type,
            "status": "DRAFT",
            "version_label": ver_label,
            "version_major": ver_major,
            "version_minor": ver_minor,
            "current_file_path": active_path,
            "created_at": now,
            "updated_at": now,
            "next_review": next_review,
            "owner_user_id": user_id or None,
        }
        known = set(self._known_columns("documents"))
        filtered = {k: v for k, v in candidate_values.items() if k in known}

        cols = list(filtered.keys()); placeholders = ",".join(["?"] * len(cols))
        sql = f"INSERT INTO documents({','.join(cols)}) VALUES({placeholders})"
        self._conn.execute(sql, [filtered[c] for c in cols])
        self._conn.commit()

        # Best-effort Kommentare auslesen
        try:
            _meta, comments = extract_core_and_comments(active_path)
            if comments:
                rows = [(new_id, str(c.get("author") or ""), str(c.get("date") or ""), str(c.get("text") or ""), str(c.get("version_label") or ver_label)) for c in comments]
                self._conn.executemany("INSERT INTO comments(doc_id,author,date,text,version_label) VALUES(?,?,?,?,?)", rows)
                self._conn.commit()
        except Exception:
            pass

        rec = self.get(new_id)
        if rec: return rec
        row = self._conn.execute("SELECT * FROM documents WHERE doc_id=?", (new_id,)).fetchone()
        return self._row_to_record(row) if row else DocumentRecord(
            doc_id=DocumentId(value=new_id), title=title or "", doc_type=doc_type,
            status=DocumentStatus.DRAFT, version_major=ver_major, version_minor=ver_minor
        )

    def update_metadata(self, data: Dict[str, Any], user_id: Optional[str]) -> None:
        doc_id = str(data.get("doc_id") or "").strip()
        if not doc_id: raise ValueError("update_metadata: 'doc_id' missing")

        fields: Dict[str, Any] = {}
        for k in ("title", "doc_type", "next_review"):
            if k in data and data[k] is not None: fields[k] = data[k]

        has_vmj = self._has_column("documents", "version_major")
        has_vmn = self._has_column("documents", "version_minor")
        has_vlabel = self._has_column("documents", "version_label")

        if ("version_major" in data) or ("version_minor" in data):
            vmj = int(data.get("version_major", 1) or 1); vmn = int(data.get("version_minor", 0) or 0)
            if has_vmj: fields["version_major"] = vmj
            if has_vmn: fields["version_minor"] = vmn
            if has_vlabel and "version_label" not in data: fields["version_label"] = f"{vmj}.{vmn}"
        elif "version_label" in data and data["version_label"]:
            label = str(data["version_label"])
            try: mj_s, mn_s = label.split(".", 1); mj, mn = int(mj_s), int(mn_s)
            except Exception: mj, mn = 1, 0
            if has_vlabel: fields["version_label"] = label
            if has_vmj: fields["version_major"] = mj
            if has_vmn: fields["version_minor"] = mn

        if not fields: return
        fields["updated_at"] = _safe_iso_now()
        known = set(self._known_columns("documents"))
        filtered = {k: v for k, v in fields.items() if k in known}
        sets = [f"{k}=?" for k in filtered.keys()]
        args = list(filtered.values()) + [doc_id]
        self._conn.execute(f"UPDATE documents SET {', '.join(sets)} WHERE doc_id=?", args)
        self._conn.commit()

    # ------------------------------ status & logging
    def update_status(self, doc_id: str, new_status: DocumentStatus) -> None:
        self._conn.execute(
            "UPDATE documents SET status=?, updated_at=? WHERE doc_id=?",
            ((new_status.name if hasattr(new_status, "name") else str(new_status)), _safe_iso_now(), doc_id)
        )
        self._conn.commit()

    def _log_status_change(self, doc_id: str, old_status: str, new_status: str, user_id: Optional[str], reason: Optional[str]) -> None:
        try:
            self._conn.execute(
                "INSERT INTO status_log(doc_id,old_status,new_status,user_id,reason,changed_at) VALUES(?,?,?,?,?,?)",
                (doc_id, old_status, new_status, user_id, reason, _safe_iso_now())
            )
            self._conn.commit()
        except Exception:
            pass

    def set_status(self, doc_id: str, new_status: DocumentStatus, user_id: Optional[str] = None, reason: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        rec = self.get(doc_id)
        if not rec: return False, f"Document not found: {doc_id}"

        old_status = getattr(rec.status, "name", str(rec.status))
        new_status_s = getattr(new_status, "name", str(new_status))

        new_path = rec.current_file_path
        if new_status_s in ("ARCHIVED", "OBSOLETE"):
            try:
                if rec.current_file_path and os.path.isfile(rec.current_file_path):
                    dest_dir = os.path.join(self._archived_dir(), doc_id); os.makedirs(dest_dir, exist_ok=True)
                    ts = datetime.now().strftime("%Y%m%d-%H%M%S"); base = os.path.basename(rec.current_file_path)
                    dest = os.path.join(dest_dir, f"{base}.{ts}.archived"); shutil.move(rec.current_file_path, dest); new_path = dest
            except Exception:
                new_path = rec.current_file_path

        fields: Dict[str, Any] = {"status": new_status_s, "updated_at": _safe_iso_now()}
        if new_path != rec.current_file_path: fields["current_file_path"] = new_path
        if new_status_s in ("ARCHIVED", "OBSOLETE") and self._has_column("documents", "obsoleted_at"):
            fields["obsoleted_at"] = _safe_iso_now()

        known = set(self._known_columns("documents"))
        filtered = {k: v for k, v in fields.items() if k in known}
        sets = [f"{k}=?" for k in filtered.keys()]
        args = list(filtered.values()) + [doc_id]
        self._conn.execute(f"UPDATE documents SET {', '.join(sets)} WHERE doc_id=?", args)
        self._conn.commit()

        if reason:
            version_label = f"{rec.version_major}.{rec.version_minor}"
            try:
                self._conn.execute("INSERT INTO comments(doc_id,author,date,text,version_label) VALUES(?,?,?,?,?)",
                                   (doc_id, user_id or "", _safe_iso_now(), reason, version_label))
                self._conn.commit()
            except Exception:
                pass

        self._log_status_change(doc_id, old_status, new_status_s, user_id, reason)
        return True, None

    # ------------------------------ workflow persistence (dual-mode)
    def set_workflow_active(self, doc_id: str, active: bool, user_id: Optional[str] = None) -> None:
        now = _safe_iso_now()
        if self._has_column("documents", "workflow_active"):
            if active:
                self._conn.execute(
                    "UPDATE documents SET workflow_active=1, workflow_started_by=COALESCE(workflow_started_by, ?), workflow_started_at=COALESCE(workflow_started_at, ?), updated_at=? WHERE doc_id=?",
                    (user_id, now, now, doc_id))
            else:
                self._conn.execute("UPDATE documents SET workflow_active=0, updated_at=? WHERE doc_id=?", (now, doc_id))
        else:
            # workflow_state upsert
            cur = self._conn.cursor()
            if active:
                cur.execute("INSERT INTO workflow_state(doc_id,active,started_by,started_at) VALUES(?,?,?,?) "
                            "ON CONFLICT(doc_id) DO UPDATE SET active=excluded.active, started_by=COALESCE(workflow_state.started_by, excluded.started_by), started_at=COALESCE(workflow_state.started_at, excluded.started_at)",
                            (doc_id, 1, user_id, now))
            else:
                cur.execute("INSERT INTO workflow_state(doc_id,active) VALUES(?,?) "
                            "ON CONFLICT(doc_id) DO UPDATE SET active=excluded.active",
                            (doc_id, 0))
        self._conn.commit()

    def is_workflow_active(self, doc_id: str) -> bool:
        if self._has_column("documents", "workflow_active"):
            row = self._conn.execute("SELECT workflow_active FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
            if not row: return False
            try: return int(row["workflow_active"] or 0) == 1
            except Exception: return False
        row = self._conn.execute("SELECT active FROM workflow_state WHERE doc_id=?", (doc_id,)).fetchone()
        if not row: return False
        try: return int(row["active"] or 0) == 1
        except Exception: return False

    # ------------------------------ PDF utils
    def _active_pdf_path(self, doc_id: str) -> str:
        return os.path.join(self._active_dir(doc_id), "current.pdf")

    def _active_docx_path(self, doc_id: str) -> Optional[str]:
        d = self._active_dir(doc_id)
        cands = [os.path.join(d, n) for n in os.listdir(d) if n.lower().endswith(".docx")]
        cands = sorted(cands, key=lambda p: (not os.path.basename(p).startswith(f"{doc_id}_"), p))
        return cands[0] if cands else None

    def _convert_docx_to_pdf_clean(self, docx_path: str, out_pdf: str) -> bool:
        # 1) Word-COM (ohne Markups)
        try:
            import win32com.client  # type: ignore
            import pythoncom  # type: ignore
            pythoncom.CoInitialize()
            word = win32com.client.Dispatch("Word.Application"); word.Visible = False
            try:
                doc = word.Documents.Open(docx_path, ReadOnly=True)
                try:
                    view = word.ActiveWindow.View
                    try: view.ShowRevisionsAndComments = False
                    except Exception: pass
                    try: view.RevisionsView = 0  # wdRevisionsViewFinal
                    except Exception: pass
                    try: word.Options.PrintRevisions = False
                    except Exception: pass
                except Exception:
                    pass
                wdFormatPDF = 17
                doc.SaveAs(out_pdf, FileFormat=wdFormatPDF)
                doc.Close(False); word.Quit()
                return os.path.isfile(out_pdf)
            finally:
                try: word.Quit()
                except Exception: pass
                try: pythoncom.CoUninitialize()
                except Exception: pass
        except Exception:
            pass
        # 2) docx2pdf
        try:
            from docx2pdf import convert  # type: ignore
            convert(docx_path, out_pdf)
            return os.path.isfile(out_pdf)
        except Exception:
            pass
        # 3) Fallback (verhindert Crash)
        try:
            shutil.copy2(docx_path, out_pdf); return os.path.isfile(out_pdf)
        except Exception:
            return False

    def generate_review_pdf(self, doc_id: str) -> Optional[str]:
        rec = self.get(doc_id)
        if not rec: return None
        dst = self._active_pdf_path(doc_id); os.makedirs(os.path.dirname(dst), exist_ok=True)

        if rec.current_file_path and rec.current_file_path.lower().endswith(".pdf") and os.path.isfile(rec.current_file_path):
            if os.path.abspath(rec.current_file_path) != os.path.abspath(dst):
                try: shutil.copy2(rec.current_file_path, dst)
                except Exception: dst = rec.current_file_path
            try:
                self._conn.execute("UPDATE documents SET current_file_path=?, updated_at=? WHERE doc_id=?",
                                   (dst, _safe_iso_now(), doc_id)); self._conn.commit()
            except Exception: pass
            return dst

        docx = self._active_docx_path(doc_id)
        if not docx and rec.current_file_path and rec.current_file_path.lower().endswith(".docx") and os.path.isfile(rec.current_file_path):
            docx = rec.current_file_path
        if not (docx and os.path.isfile(docx)): return None

        ok = self._convert_docx_to_pdf_clean(docx, dst)
        if not ok: return None
        try:
            self._conn.execute("UPDATE documents SET current_file_path=?, updated_at=? WHERE doc_id=?",
                               (dst, _safe_iso_now(), doc_id)); self._conn.commit()
        except Exception: pass
        return dst if os.path.isfile(dst) else None

    def export_pdf_with_version_suffix(self, doc_id: str) -> Optional[str]:
        rec = self.get(doc_id)
        if not rec: return None
        src = rec.current_file_path or ""
        if not (src and src.lower().endswith(".pdf") and os.path.isfile(src)):
            src = self.generate_review_pdf(doc_id) or ""
        if not (src and os.path.isfile(src)): return None
        version_label = f"{rec.version_major}.{rec.version_minor}"
        dst_dir = self._version_dir(doc_id, version_label)
        dst = os.path.join(dst_dir, f"{doc_id}_v{version_label}.pdf")
        os.makedirs(dst_dir, exist_ok=True); shutil.copy2(src, dst); return dst

    def attach_signed_pdf(self, doc_id: str, signed_pdf_path: str, step: str, user_id: Optional[str] = None, reason: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        if not (signed_pdf_path and os.path.isfile(signed_pdf_path)): return False, None
        rec = self.get(doc_id)
        if not rec: return False, None
        step_norm = (step or "").strip().lower(); now = _safe_iso_now()
        if step_norm == "publish":
            version_label = f"{rec.version_major}.{rec.version_minor}"
            vdir = self._version_dir(doc_id, version_label)
            base = f"{doc_id}_v{version_label}_signed.pdf"
            dst = os.path.join(vdir, base)
        else:
            dst = self._active_pdf_path(doc_id)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        try: shutil.copy2(signed_pdf_path, dst)
        except Exception as ex: return False, str(ex)
        try:
            self._conn.execute("UPDATE documents SET current_file_path=?, updated_at=? WHERE doc_id=?",
                               (dst, now, doc_id)); self._conn.commit()
        except Exception: pass
        try:
            self._conn.execute("INSERT INTO signatures(doc_id, step, user_id, signed_at) VALUES(?,?,?,?)",
                               (doc_id, step_norm, user_id or "", now)); self._conn.commit()
        except Exception: pass
        if reason:
            try:
                version_label = f"{rec.version_major}.{rec.version_minor}"
                self._conn.execute("INSERT INTO comments(doc_id,author,date,text,version_label) VALUES(?,?,?,?,?)",
                                   (doc_id, user_id or "", now, reason, version_label)); self._conn.commit()
            except Exception: pass
        return True, dst

    # ------------------------------ misc helpers
    def get_owner(self, doc_id: str) -> Optional[str]:
        row = self._conn.execute("SELECT owner_user_id FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
        return (row["owner_user_id"] if row and "owner_user_id" in row.keys() else None)

    def get_docx_comments_for_version(self, doc_id: str, version_label: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT author,date,text,version_label FROM comments WHERE doc_id=? AND (? IS NULL OR version_label=?) ORDER BY date ASC",
            (doc_id, version_label, version_label),
        ).fetchall()
        if rows:
            return [{"author": r["author"], "date": r["date"], "text": r["text"], "version_label": r["version_label"]} for r in rows]
        rec = self.get(doc_id); path = getattr(rec, "current_file_path", None) if rec else None
        out: List[Dict[str, Any]] = []
        if path and os.path.isfile(path):
            try:
                _meta, found = extract_core_and_comments(path)
                if found:
                    vlabel = version_label or (f"{rec.version_major}.{rec.version_minor}" if rec else "1.0")
                    batch = []
                    for c in found:
                        a = str(c.get("author") or ""); d = str(c.get("date") or ""); t = str(c.get("text") or ""); vl = str(c.get("version_label") or vlabel)
                        batch.append((doc_id, a, d, t, vl)); out.append({"author": a, "date": d, "text": t, "version_label": vl})
                    self._conn.executemany("INSERT INTO comments(doc_id,author,date,text,version_label) VALUES(?,?,?,?,?)", batch); self._conn.commit()
            except Exception: pass
        return out

    def check_in(self, doc_id: str, user_id: str, src_docx_path: str, note: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        if not (src_docx_path and os.path.isfile(src_docx_path)): return False, "Quelle nicht gefunden."
        rec = self.get(doc_id)
        if not rec: return False, "Dokument nicht gefunden."
        dst = os.path.join(self._active_dir(doc_id), "current.docx"); os.makedirs(os.path.dirname(dst), exist_ok=True)
        try: shutil.copy2(src_docx_path, dst)
        except Exception as ex: return False, str(ex)
        try:
            self._conn.execute("UPDATE documents SET current_file_path=?, updated_at=? WHERE doc_id=?",
                               (dst, _safe_iso_now(), doc_id)); self._conn.commit()
        except Exception: pass
        if note:
            try:
                vlabel = f"{rec.version_major}.{rec.version_minor}"
                self._conn.execute("INSERT INTO comments(doc_id,author,date,text,version_label) VALUES(?,?,?,?,?)",
                                   (doc_id, user_id or "", _safe_iso_now(), note, vlabel)); self._conn.commit()
            except Exception: pass
        return True, None

    # ------------------------------ id generation
    def _new_doc_id(self) -> str:
        year = datetime.now().year; prefix = self._cfg.id_prefix.strip(); pattern = self._cfg.id_pattern
        like = f"{prefix}-{year}-%"
        rows = self._conn.execute("SELECT doc_id FROM documents WHERE doc_id LIKE ? ORDER BY doc_id DESC LIMIT 1", (like,)).fetchall()
        seq = 0
        if rows:
            last = rows[0]["doc_id"]; m = re.search(rf"^{re.escape(prefix)}-{year}-(\d+)$", last)
            if m: seq = int(m.group(1))
        seq += 1
        doc_id = f"{prefix}-" + pattern.format(YYYY=year, seq=seq)
        while self._conn.execute("SELECT 1 FROM documents WHERE doc_id=?", (doc_id,)).fetchone():
            seq += 1; doc_id = f"{prefix}-" + pattern.format(YYYY=year, seq=seq)
        return doc_id
