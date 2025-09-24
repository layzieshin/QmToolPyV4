"""
Repository with:
- robust status mapping (case-insensitive)
- per-document assignees
- DOCX comments ingest
- PDF conversion helpers
- signatures recording (via AppContext.signature() – no PNG dialog required)
- read receipts (who read which version)

This module coordinates SQLite metadata and on-disk file storage for the
Document Control feature. It supports versioning, audit trails, workflow
assignments, and integration with an external signature service via
AppContext.signature().

Note: Integrate paths/imports if your project structure differs.
"""

from __future__ import annotations

import os
import re
import shutil
import sqlite3
from datetime import datetime, timedelta
from dataclasses import asdict
from typing import Optional, TypedDict, List, Dict, Any

# AppContext is optional at import-time; repository remains usable without signature API.
try:
    from core.common.app_context import AppContext  # type: ignore
except Exception:
    class AppContext:  # minimal shim to avoid hard dependency
        @staticmethod
        def signature():
            raise RuntimeError("Signature API unavailable")

from documents.models.document_models import DocumentRecord, DocumentStatus, DocumentId
from .audit_log import AuditLog
from .id_generator import IdGenerator
from .pdf_tools import make_controlled_copy, stamp_signature
from documents.logic.word_tools import extract_core_and_comments, set_core_properties, create_from_template
from documents.logic.doc_convert import convert_to_pdf


class RepoConfig(TypedDict):
    root_path: str
    db_path: str
    id_prefix: str
    id_pattern: str
    review_months: int
    watermark_copy: str


class DocumentsRepository:
    """
    Coordinates SQLite metadata and on-disk file storage. Supports versioning,
    workflow role assignments, extracted comments, signature stamping via
    AppContext.signature(), and read receipts.
    """

    # ----------------------------- lifecycle --------------------------------

    def __init__(self, cfg: RepoConfig) -> None:
        self._cfg = cfg
        os.makedirs(cfg["root_path"], exist_ok=True)
        os.makedirs(os.path.dirname(cfg["db_path"]), exist_ok=True)
        self._conn = sqlite3.connect(cfg["db_path"])
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._audit = AuditLog(self._conn)
        self._idg = IdGenerator(self._conn, cfg["id_prefix"], cfg["id_pattern"])
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Ensure that all required tables exist."""
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                doc_type TEXT NOT NULL,
                status TEXT NOT NULL,
                version_major INTEGER NOT NULL,
                version_minor INTEGER NOT NULL,
                current_file_path TEXT,
                area TEXT,
                process TEXT,
                valid_from TEXT,
                next_review TEXT,
                obsoleted_at TEXT,
                created_by TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                change_note TEXT,
                norm_refs TEXT,
                tags TEXT,
                locked_by TEXT,
                locked_at TEXT
            );

            CREATE TABLE IF NOT EXISTS versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id TEXT NOT NULL,
                version_label TEXT NOT NULL,
                file_path TEXT,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                change_note TEXT,
                FOREIGN KEY(doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS signatures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id TEXT NOT NULL,
                step TEXT NOT NULL,
                user_id TEXT NOT NULL,
                reason TEXT,
                signed_at TEXT NOT NULL,
                file_path TEXT,
                FOREIGN KEY(doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS doc_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id TEXT NOT NULL,
                role TEXT NOT NULL,
                user_id TEXT NOT NULL,
                UNIQUE(doc_id, role, user_id),
                FOREIGN KEY(doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS doc_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id TEXT NOT NULL,
                version_label TEXT NOT NULL,
                author TEXT,
                date TEXT,
                text TEXT,
                FOREIGN KEY(doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS read_receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id TEXT NOT NULL,
                version_label TEXT NOT NULL,
                user_id TEXT NOT NULL,
                read_at TEXT NOT NULL,
                UNIQUE(doc_id, version_label, user_id),
                FOREIGN KEY(doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
            );
            """
        )

    # ----------------------------- helpers ----------------------------------

    def _now(self) -> datetime:
        return datetime.utcnow()

    def _doc_dir(self, doc_id: str) -> str:
        return os.path.join(self._cfg["root_path"], doc_id)

    def _ver_dir(self, doc_id: str, version_label: str) -> str:
        return os.path.join(self._doc_dir(doc_id), f"v{version_label}")

    def _store_file(self, src: str, dst_dir: str, rename_to: Optional[str] = None) -> str:
        os.makedirs(dst_dir, exist_ok=True)
        filename = rename_to or os.path.basename(src)
        dst = os.path.join(dst_dir, filename)
        shutil.copyfile(src, dst)
        return dst

    # ---- filename normalization (single source of truth for naming rules) ---

    @staticmethod
    def _strip_signed_and_version_tokens(name_wo_ext: str) -> str:
        """
        Remove all occurrences of '_signed' (case-insensitive) anywhere in the
        base name and a trailing version pattern like '_v1.2.3'.
        Collapse duplicate underscores.
        """
        n = re.sub(r'(?i)_signed', '', name_wo_ext)
        n = re.sub(r'_v\d+(?:\.\d+)*$', '', n)
        n = re.sub(r'__+', '_', n).strip('_')
        return n

    @staticmethod
    def _make_signed_filename(base_wo_ext: str, version_label: Optional[str]) -> str:
        """
        Build final file name (with .pdf):
        - Always exactly one '_signed'
        - If version_label is given -> suffix '_v<version>'
        Example: base -> base_signed_v1.3.pdf
        """
        core = DocumentsRepository._strip_signed_and_version_tokens(base_wo_ext)
        if version_label:
            return f"{core}_signed_v{version_label}.pdf"
        return f"{core}_signed.pdf"

    # ----------------------------- status utils -----------------------------

    @staticmethod
    def _status_to_enum(val: Any) -> DocumentStatus:
        if isinstance(val, DocumentStatus):
            return val
        s = str(val or "").strip()
        if not s:
            raise ValueError("Empty status")
        key = s.upper().replace("-", "_").replace(" ", "_")
        try:
            return DocumentStatus[key]
        except Exception:
            pass
        for st in DocumentStatus:
            if str(st.value).lower() == s.lower():
                return st
        raise ValueError(f"Unknown status: {val}")

    # ----------------------------- id/title parsing -------------------------

    @staticmethod
    def _parse_id_title_from_filename(path: str) -> tuple[Optional[str], Optional[str]]:
        name = os.path.splitext(os.path.basename(path))[0]
        if "_" in name:
            left, right = name.split("_", 1)
            if left.strip() and right.strip():
                return left.strip(), right.strip()
        return None, None

    def _ensure_unique_doc_id(self, desired: Optional[str]) -> str:
        if not desired:
            return self._idg.next_id()
        row = self._conn.execute("SELECT 1 FROM documents WHERE doc_id=?", (desired,)).fetchone()
        if not row:
            return desired
        i = 1
        while True:
            cand = f"{desired}-{i:03d}"
            row = self._conn.execute("SELECT 1 FROM documents WHERE doc_id=?", (cand,)).fetchone()
            if not row:
                return cand
            i += 1

    # ----------------------------- CRUD ------------------------------------

    def create_from_file(
        self,
        *,
        title: str | None,
        doc_type: str,
        user_id: str | None,
        src_file: str,
        area: str | None = None,
        process: str | None = None,
        change_note: str | None = None,
    ) -> DocumentRecord:
        parsed_id, parsed_title = self._parse_id_title_from_filename(src_file)
        doc_id = self._ensure_unique_doc_id(parsed_id)
        now = self._now()
        version_major, version_minor = 1, 0
        ver_label = f"{version_major}.{version_minor}"
        final_title = (parsed_title or title or os.path.splitext(os.path.basename(src_file))[0]).strip()

        fpath = self._store_file(src_file, self._ver_dir(doc_id, ver_label))
        # If DOCX: set metadata and ingest comments
        if fpath.lower().endswith(".docx"):
            try:
                set_core_properties(fpath, props={
                    "author": user_id or "",
                    "last_modified_by": user_id or "",
                    "title": final_title,
                })
                _, comments = extract_core_and_comments(fpath)
                self._ingest_comments(doc_id, ver_label, comments)
            except Exception:
                pass

        next_review_dt = now + timedelta(days=30 * int(self._cfg["review_months"]))
        self._conn.execute(
            """
            INSERT INTO documents (doc_id,title,doc_type,status,version_major,version_minor,current_file_path,
                                   area,process,valid_from,next_review,created_by,created_at,updated_at,change_note)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                doc_id,
                final_title,
                doc_type,
                DocumentStatus.DRAFT.name,
                version_major,
                version_minor,
                fpath,
                area,
                process,
                now.isoformat(timespec="seconds"),
                next_review_dt.isoformat(timespec="seconds"),
                user_id,
                now.isoformat(timespec="seconds"),
                now.isoformat(timespec="seconds"),
                change_note,
            ),
        )
        self._conn.execute(
            """
            INSERT INTO versions (doc_id,version_label,file_path,created_at,created_by,change_note)
            VALUES (?,?,?,?,?,?)
            """,
            (doc_id, ver_label, fpath, now.isoformat(timespec="seconds"), user_id or "", change_note),
        )
        self._audit.write(doc_id, "create", user_id, {"title": final_title, "doc_type": doc_type})
        self._conn.commit()
        return self.get(doc_id)

    def create_from_template(
        self,
        *,
        template_path: str,
        target_id: Optional[str],
        title: str,
        doc_type: str,
        user_id: str | None,
    ) -> DocumentRecord:
        doc_id = self._ensure_unique_doc_id(target_id)
        now = self._now()
        version_major, version_minor = 1, 0
        ver_label = f"{version_major}.{version_minor}"
        out_dir = self._ver_dir(doc_id, ver_label)
        out_name = f"{doc_id}_{title}.docx"
        out_path = os.path.join(out_dir, out_name)
        create_from_template(
            template_path,
            out_path,
            props={"author": user_id or "", "last_modified_by": user_id or "", "title": title, "revision": 1},
        )
        _, comments = extract_core_and_comments(out_path)
        self._ingest_comments(doc_id, ver_label, comments)
        next_review_dt = now + timedelta(days=30 * int(self._cfg["review_months"]))
        self._conn.execute(
            """
            INSERT INTO documents (doc_id,title,doc_type,status,version_major,version_minor,current_file_path,
                                   valid_from,next_review,created_by,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                doc_id,
                title,
                doc_type,
                DocumentStatus.DRAFT.name,
                version_major,
                version_minor,
                out_path,
                now.isoformat(timespec="seconds"),
                next_review_dt.isoformat(timespec="seconds"),
                user_id,
                now.isoformat(timespec="seconds"),
                now.isoformat(timespec="seconds"),
            ),
        )
        self._conn.execute(
            """
            INSERT INTO versions (doc_id,version_label,file_path,created_at,created_by,change_note)
            VALUES (?,?,?,?,?,?)
            """,
            (doc_id, ver_label, out_path, now.isoformat(timespec="seconds"), user_id or "", None),
        )
        self._audit.write(doc_id, "create_from_template", user_id, {"template": os.path.basename(template_path)})
        self._conn.commit()
        return self.get(doc_id)

    def get(self, doc_id: str) -> DocumentRecord:
        row = self._conn.execute("SELECT * FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
        if not row:
            raise KeyError(f"Document not found: {doc_id}")
        return self._map_record(dict(row))

    def list(self, status: Optional[DocumentStatus] = None, text: Optional[str] = None) -> list[DocumentRecord]:
        sql = "SELECT * FROM documents"
        args: list[object] = []
        conds: list[str] = []
        if status:
            conds.append("UPPER(status)=?"); args.append(status.name)
        if text:
            conds.append("(title LIKE ? OR doc_id LIKE ?)"); args.extend([f"%{text}%", f"%{text}%"])
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY updated_at DESC"
        rows = self._conn.execute(sql, tuple(args)).fetchall()
        return [self._map_record(dict(r)) for r in rows]

    def update_metadata(self, doc: DocumentRecord, user_id: str | None) -> None:
        d = asdict(doc)
        self._conn.execute(
            """
            UPDATE documents SET title=?, doc_type=?, area=?, process=?, next_review=?, change_note=?,
                                 updated_at=? WHERE doc_id=?
            """,
            (
                d["title"],
                d["doc_type"],
                d["area"],
                d["process"],
                d["next_review"].isoformat(timespec="seconds") if d["next_review"] else None,
                d["change_note"],
                self._now().isoformat(timespec="seconds"),
                doc.doc_id.value,
            ),
        )
        self._audit.write(doc.doc_id.value, "update_metadata", user_id, {"title": d["title"], "doc_type": d["doc_type"]})
        self._conn.commit()

    # ----------------------------- check-in/out -----------------------------

    def check_out(self, doc_id: str, user_id: str) -> bool:
        row = self._conn.execute("SELECT locked_by FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
        if row and row["locked_by"]:
            return False
        now = self._now().isoformat(timespec="seconds")
        self._conn.execute("UPDATE documents SET locked_by=?, locked_at=? WHERE doc_id=?", (user_id, now, doc_id))
        self._audit.write(doc_id, "check_out", user_id, {})
        self._conn.commit()
        return True

    def check_in(
        self,
        doc_id: str,
        user_id: str,
        src_file: Optional[str],
        change_note: Optional[str],
    ) -> DocumentRecord:
        """
        Content check-in (new file or metadata-only): bumps minor version.
        """
        cur = self._conn.execute(
            "SELECT version_major,version_minor,current_file_path FROM documents WHERE doc_id=?",
            (doc_id,),
        ).fetchone()
        if not cur:
            raise KeyError("Document not found")

        maj, minor = int(cur["version_major"]), int(cur["version_minor"])
        new_minor = minor + 1
        new_path = None

        if src_file:
            if src_file.lower().endswith(".docx"):
                try:
                    core, comments = extract_core_and_comments(src_file)
                    rev = int(core.get("revision") or 0)
                    if rev and rev > minor:
                        new_minor = rev
                    self._ingest_comments(doc_id, f"{maj}.{new_minor}", comments)
                except Exception:
                    pass
            new_path = self._store_file(src_file, self._ver_dir(doc_id, f"{maj}.{new_minor}"))

        now = self._now().isoformat(timespec="seconds")
        self._conn.execute(
            """
            UPDATE documents SET version_major=?, version_minor=?, current_file_path=?, locked_by=NULL, locked_at=NULL,
                                 updated_at=?, change_note=? WHERE doc_id=?
            """,
            (maj, new_minor, new_path, now, change_note, doc_id),
        )
        new_label = f"{maj}.{new_minor}"
        self._conn.execute(
            """
            INSERT INTO versions (doc_id,version_label,file_path,created_at,created_by,change_note)
            VALUES (?,?,?,?,?,?)
            """,
            (doc_id, new_label, new_path, now, user_id, change_note),
        )
        self._audit.write(doc_id, "check_in", user_id, {"version": new_label})
        self._conn.commit()
        return self.get(doc_id)

    # ----------------------------- status transitions -----------------------

    def set_status(self, doc_id: str, target: DocumentStatus, user_id: Optional[str], change_note: Optional[str]) -> DocumentRecord:
        now = self._now()
        obsoleted_at = now.isoformat(timespec="seconds") if target == DocumentStatus.OBSOLETE else None
        self._conn.execute(
            "UPDATE documents SET status=?, updated_at=?, change_note=?, obsoleted_at=? WHERE doc_id=?",
            (target.name, now.isoformat(timespec="seconds"), change_note, obsoleted_at, doc_id),
        )
        self._audit.write(doc_id, f"status_{target.name}", user_id, {"change_note": change_note})
        self._conn.commit()
        return self.get(doc_id)

    # ----------------------------- PDF helpers ------------------------------

    def generate_review_pdf(self, doc_id: str) -> Optional[str]:
        row = self._conn.execute("SELECT current_file_path FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
        if not row or not row["current_file_path"]:
            return None
        src = str(row["current_file_path"])
        out_pdf = os.path.join(os.path.dirname(src), os.path.splitext(os.path.basename(src))[0] + ".pdf")
        pdf_path = convert_to_pdf(src, out_pdf)
        if pdf_path:
            now = self._now().isoformat(timespec="seconds")
            self._conn.execute("UPDATE documents SET current_file_path=?, updated_at=? WHERE doc_id=?", (pdf_path, now, doc_id))
            self._conn.commit()
        return pdf_path

    def export_pdf_with_version_suffix(self, doc_id: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT current_file_path,version_major,version_minor FROM documents WHERE doc_id=?",
            (doc_id,),
        ).fetchone()
        if not row or not row["current_file_path"]:
            return None
        src = str(row["current_file_path"])
        ver_label = f"{int(row['version_major'])}.{int(row['version_minor'])}"
        base = os.path.splitext(os.path.basename(src))[0]
        out_pdf = os.path.join(os.path.dirname(src), f"{base}_v{ver_label}.pdf")
        return convert_to_pdf(src, out_pdf)

    # ----------------------------- signature integration --------------------

    def _default_placement(self):
        class P:
            page_index = -1
            x = 460
            y = 80
            target_width = 180
        return P()

    def attach_signed_pdf(self, doc_id: str, signed_pdf: str, step: str, user_id: str, reason: str) -> str:
        """
        Attach a (externally) signed PDF to the *current* version without bumping version numbers.

        Naming rules:
          - exactly one '_signed'
          - version suffix only for final publish: '_signed_v<maj.min>.pdf'

        Updates 'documents.current_file_path' and the latest 'versions.file_path' for the current version label.
        Also appends a row to 'signatures' and writes an audit entry.

        Returns: absolute path to the normalized stored PDF.
        """
        if not (signed_pdf and os.path.isfile(signed_pdf)):
            raise FileNotFoundError("Signed PDF not found.")

        cur = self._conn.execute(
            "SELECT version_major,version_minor FROM documents WHERE doc_id=?",
            (doc_id,),
        ).fetchone()
        if not cur:
            raise KeyError(f"Document not found: {doc_id}")

        maj, minor = int(cur["version_major"]), int(cur["version_minor"])
        version_label = f"{maj}.{minor}"

        step_norm = (step or "").strip().lower()
        use_version_suffix = step_norm in {"publish"}  # only final publish receives version suffix

        base_in = os.path.splitext(os.path.basename(signed_pdf))[0]
        target_name = self._make_signed_filename(base_in, version_label if use_version_suffix else None)

        out_dir = self._ver_dir(doc_id, version_label)
        os.makedirs(out_dir, exist_ok=True)
        target_path = os.path.join(out_dir, target_name)

        if os.path.abspath(signed_pdf) != os.path.abspath(target_path):
            shutil.copyfile(signed_pdf, target_path)

        now = self._now().isoformat(timespec="seconds")
        # Update current document pointer
        self._conn.execute(
            "UPDATE documents SET current_file_path=?, updated_at=? WHERE doc_id=?",
            (target_path, now, doc_id),
        )
        # Ensure the versions row for this version_label points to the normalized file
        self._conn.execute(
            """
            UPDATE versions
               SET file_path=?
             WHERE id = (
                 SELECT id FROM versions
                  WHERE doc_id=? AND version_label=?
                  ORDER BY id DESC
                  LIMIT 1
             )
            """,
            (target_path, doc_id, version_label),
        )
        # Signatures trail
        self._conn.execute(
            """
            INSERT INTO signatures(doc_id,step,user_id,reason,signed_at,file_path)
            VALUES (?,?,?,?,?,?)
            """,
            (doc_id, step_norm, user_id or "", reason or "", now, target_path),
        )
        self._audit.write(doc_id, "signature", user_id, {"step": step_norm, "file": os.path.basename(target_path)})
        self._conn.commit()
        return target_path

    def record_signature(
        self,
        doc_id: str,
        step: str,
        user_id: str,
        reason: Optional[str],
        signature_png: Optional[bytes],
    ) -> None:
        """
        Record a signature for allowed workflow steps by stamping the current PDF
        via the signature API (preferred) or PNG fallback, and attach the result
        to the *current* version without changing version numbers.

        Allowed steps: submit_review, request_approval, publish
        - Only 'publish' will get a filename with '_signed_v<maj.min>.pdf'
        - Other steps get '<name>_signed.pdf'
        """
        step_norm = (step or "").strip().lower()
        allowed = {"submit_review", "request_approval", "publish"}
        if step_norm not in allowed:
            # No-op but audit for traceability
            self._audit.write(doc_id, "signature_skipped", user_id, {"step": step_norm})
            self._conn.commit()
            return

        row = self._conn.execute(
            "SELECT current_file_path FROM documents WHERE doc_id=?",
            (doc_id,),
        ).fetchone()
        if not row:
            self._audit.write(doc_id, "signature_failed", user_id, {"step": step_norm, "err": "doc_missing"})
            self._conn.commit()
            return

        src_pdf = (row["current_file_path"] or "").strip()
        if not (src_pdf and src_pdf.lower().endswith(".pdf") and os.path.isfile(src_pdf)):
            self._audit.write(doc_id, "signature_failed", user_id, {"step": step_norm, "err": "no_pdf"})
            self._conn.commit()
            return

        # Try external signature API first
        signed_path: Optional[str] = None
        try:
            api = AppContext.signature()
            # Placement discovery
            placement = None
            for meth in ("default_placement", "placement_default", "make_default_placement"):
                if hasattr(api, meth):
                    try:
                        placement = getattr(api, meth)()
                        break
                    except Exception:
                        placement = None
            if placement is None:
                placement = self._default_placement()
            try:
                out = api.sign_pdf(input_path=src_pdf, placement=placement, reason=reason,
                                   use_user_signature=True, raw_signature_png=signature_png)
            except TypeError:
                # Older API shape
                out = api.sign_pdf(src_pdf, placement, reason)

            # Normalize result to a path
            if isinstance(out, str) and os.path.isfile(out):
                signed_path = out
            elif isinstance(out, dict):
                p = out.get("out") or out.get("path") or out.get("pdf")
                if isinstance(p, str) and os.path.isfile(p):
                    signed_path = p
            elif hasattr(out, "path"):
                p = getattr(out, "path", None)
                if isinstance(p, str) and os.path.isfile(p):
                    signed_path = p
            # Some APIs modify in-place and return a truthy object
            if not signed_path and out and os.path.isfile(src_pdf):
                signed_path = src_pdf
        except Exception:
            signed_path = None

        # PNG fallback stamping if API failed but a raw signature is available
        if signed_path is None and signature_png:
            tmp_dir = os.path.dirname(src_pdf)
            tmp_out = os.path.join(tmp_dir, os.path.basename(src_pdf))
            label = f"Signed by {user_id} ({step_norm})" if user_id else f"Signature ({step_norm})"
            if stamp_signature(src_pdf, tmp_out, signature_png, label=label):
                signed_path = tmp_out

        if not signed_path:
            self._audit.write(doc_id, "signature_failed", user_id, {"step": step_norm, "err": "no_output"})
            self._conn.commit()
            return

        # Finalize: attach using normalized naming and without version bump
        self.attach_signed_pdf(doc_id, signed_path, step_norm, user_id or "", reason or "")

    # ----------------------------- controlled copies ------------------------

    def make_controlled_copy(self, doc_id: str) -> Optional[str]:
        row = self._conn.execute("SELECT current_file_path FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
        if not row or not row["current_file_path"]:
            return None
        src = str(row["current_file_path"])
        if not src.lower().endswith(".pdf"):
            return src
        out_dir = os.path.join(os.path.dirname(src), "controlled_copy")
        os.makedirs(out_dir, exist_ok=True)
        out_pdf = os.path.join(out_dir, os.path.basename(src))
        make_controlled_copy(src, out_pdf, self._cfg["watermark_copy"])
        return out_pdf

    def copy_to_destination(self, doc_id: str, dest_dir: str) -> Optional[str]:
        """Create a watermarked PDF copy in the specified destination if document is published."""
        row = self._conn.execute(
            "SELECT current_file_path,status FROM documents WHERE doc_id=?",
            (doc_id,),
        ).fetchone()
        if not row or row["status"] != DocumentStatus.PUBLISHED.name:
            return None
        src = row["current_file_path"]
        if not (src and src.lower().endswith(".pdf")):
            return None
        name = os.path.basename(src)
        out = os.path.join(dest_dir, name)
        make_controlled_copy(src, out, self._cfg["watermark_copy"])
        return out

    # ----------------------------- comments & reads -------------------------

    def _ingest_comments(self, doc_id: str, version_label: str, comments: List[Dict]) -> None:
        if not comments:
            return
        cur = self._conn.cursor()
        for c in comments:
            dt = c.get("date")
            cur.execute(
                "INSERT INTO doc_comments(doc_id,version_label,author,date,text) VALUES (?,?,?,?,?)",
                (doc_id, version_label, c.get("author"), dt.isoformat() if dt else None, c.get("text")),
            )
        self._conn.commit()

    def list_comments(self, doc_id: str, version_label: Optional[str] = None) -> list[dict]:
        sql = "SELECT author,date,text,version_label FROM doc_comments WHERE doc_id=?"
        args: list = [doc_id]
        if version_label:
            sql += " AND version_label=?"
            args.append(version_label)
        sql += " ORDER BY id ASC"
        rows = self._conn.execute(sql, tuple(args)).fetchall()
        out: list[dict] = []
        for r in rows:
            out.append(
                {
                    "author": r["author"],
                    "date": r["date"],
                    "text": r["text"],
                    "version_label": r["version_label"],
                }
            )
        return out

    # ----------------------------- assignees / tasks ------------------------

    def set_assignees(
        self, doc_id: str, *, authors: list[str] | None, reviewers: list[str], approvers: list[str]
    ) -> None:
        cur = self._conn.cursor()
        cur.execute("DELETE FROM doc_roles WHERE doc_id=?", (doc_id,))
        def ins(role: str, users: list[str] | None) -> None:
            if not users:
                return
            for u in sorted({x.strip() for x in users if str(x).strip()}):
                cur.execute(
                    "INSERT OR IGNORE INTO doc_roles(doc_id,role,user_id) VALUES (?,?,?)",
                    (doc_id, role.upper(), u),
                )
        ins("AUTHOR", authors)
        ins("REVIEWER", reviewers)
        ins("APPROVER", approvers)
        self._conn.commit()
        self._audit.write(doc_id, "set_assignees", None, {"authors": authors or [], "reviewers": reviewers, "approvers": approvers})

    def get_assignees(self, doc_id: str) -> dict[str, list[str]]:
        out = {"AUTHOR": [], "REVIEWER": [], "APPROVER": []}
        rows = self._conn.execute("SELECT role,user_id FROM doc_roles WHERE doc_id=?", (doc_id,)).fetchall()
        for r in rows:
            rl = str(r["role"]).upper()
            if rl in out:
                out[rl].append(str(r["user_id"]))
        return out

    def list_tasks_for_user(self, user_id: str) -> list[dict]:
        tasks: list[dict] = []
        rows = self._conn.execute(
            """
            SELECT d.doc_id, d.title, d.status, d.version_major, d.version_minor, d.created_by
              FROM documents d
             WHERE d.created_by = ?
                OR EXISTS (SELECT 1 FROM doc_roles r WHERE r.doc_id=d.doc_id AND r.user_id=?)
             ORDER BY d.updated_at DESC
            """,
            (user_id, user_id),
        ).fetchall()
        for r in rows:
            status = self._status_to_enum(r["status"])
            doc_id = str(r["doc_id"])
            ass = self.get_assignees(doc_id)
            next_action = None
            if status == DocumentStatus.DRAFT:
                if (user_id == (r["created_by"] or "")) or user_id in ass.get("AUTHOR", []):
                    next_action = "submit_review"
            elif status == DocumentStatus.IN_REVIEW:
                if user_id in ass.get("REVIEWER", []):
                    next_action = "request_approval"
            elif status == DocumentStatus.APPROVAL:
                if user_id in ass.get("APPROVER", []):
                    next_action = "publish"
            if next_action:
                tasks.append(
                    {
                        "doc_id": doc_id,
                        "title": str(r["title"]),
                        "status": status.name,
                        "version": f"{int(r['version_major'])}.{int(r['version_minor'])}",
                        "next_action": next_action,
                    }
                )
        return tasks

    # ----------------------------- read receipts ----------------------------

    def mark_read(self, doc_id: str, user_id: str) -> None:
        row = self._conn.execute("SELECT version_major,version_minor FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
        if not row:
            return
        ver_label = f"{int(row['version_major'])}.{int(row['version_minor'])}"
        self._conn.execute(
            "INSERT OR IGNORE INTO read_receipts(doc_id,version_label,user_id,read_at) VALUES (?,?,?,?)",
            (doc_id, ver_label, user_id, self._now().isoformat(timespec="seconds")),
        )
        self._conn.commit()

    def list_reads(self, doc_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT version_label,user_id,read_at FROM read_receipts WHERE doc_id=? ORDER BY read_at DESC",
            (doc_id,),
        ).fetchall()
        return [{"version_label": r["version_label"], "user_id": r["user_id"], "read_at": r["read_at"]} for r in rows]

    # ----------------------------- mapping ----------------------------------

    def _map_record(self, r: dict) -> DocumentRecord:
        def parse_dt(val: Optional[str]):
            if not val:
                return None
            return datetime.fromisoformat(val)
        return DocumentRecord(
            doc_id=DocumentId(str(r["doc_id"])),
            title=str(r["title"]),
            doc_type=str(r["doc_type"]),
            status=self._status_to_enum(r["status"]),
            version_major=int(r["version_major"]),
            version_minor=int(r["version_minor"]),
            current_file_path=str(r["current_file_path"]) if r["current_file_path"] else None,
            area=str(r["area"]) if r["area"] else None,
            process=str(r["process"]) if r["process"] else None,
            valid_from=parse_dt(r["valid_from"]),
            next_review=parse_dt(r["next_review"]),
            obsoleted_at=parse_dt(r["obsoleted_at"]),
            created_by=str(r["created_by"]) if r["created_by"] else None,
            created_at=parse_dt(r["created_at"]) or datetime.utcnow(),
            updated_at=parse_dt(r["updated_at"]) or datetime.utcnow(),
            change_note=str(r["change_note"]) if r["change_note"] else None,
            norm_refs=(str(r["norm_refs"]).split(",") if r["norm_refs"] else []),
            tags=(str(r["tags"]).split(",") if r["tags"] else []),
            locked_by=str(r["locked_by"]) if r["locked_by"] else None,
            locked_at=parse_dt(r["locked_at"]),
        )
