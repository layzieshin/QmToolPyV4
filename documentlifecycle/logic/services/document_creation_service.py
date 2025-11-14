"""
===============================================================================
DocumentCreationService – import/create flows + metadata defaults/persist
-------------------------------------------------------------------------------
- import_docx_copy_only(..): copy into inbox, keep original basename
- create_from_template(..): copy into drafts as .docx, keep basename
- derive_defaults_from_path(..): code/title/type (2-letter mapping)
- register_copied_docx_in_db(..): writes title/code/doc_type/description
- update_metadata(..): update key fields after dialog edits
===============================================================================
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Optional, Any, Callable

from documentlifecycle.logic.adapters.storage_paths import get_inbox_dir, get_drafts_dir
from documentlifecycle.logic.adapters.file_dialogs import ask_open_docx, ask_open_template
from documentlifecycle.logic.util.code_parser import parse_code_and_title_from_path
from documentlifecycle.models.document_type import from_two_letter_code

# Optional logging (positional args only)
try:
    from core.logging.logic.logger import logger  # type: ignore
except Exception:  # pragma: no cover
    class _NoopLogger:
        def log(self, *args, **kwargs) -> None: ...
    logger = _NoopLogger()  # type: ignore


@dataclass(frozen=True)
class ImportResult:
    ok: bool
    cancelled: bool
    src_path: Optional[str]
    dest_path: Optional[str]
    message: str
    doc_id: Optional[int] = None


@dataclass(frozen=True)
class MetadataDefaults:
    title: str
    code: Optional[str]
    doc_type: str
    description: str = ""


def _unique_dest(target_dir: Path, basename: str) -> Path:
    """
    Create a collision-free destination path in target_dir using basename,
    without adding a date prefix. We append ' (2)', ' (3)', ... before extension.
    """
    base = Path(basename)
    stem = base.stem
    ext = base.suffix
    p = target_dir / (stem + ext)
    i = 2
    while p.exists():
        p = target_dir / f"{stem} ({i}){ext}"
        i += 1
    return p


class DocumentCreationService:
    def __init__(
        self,
        open_docx_func: Callable[[Any | None], Optional[str]] = ask_open_docx,
        open_template_func: Callable[[Any | None], Optional[str]] = ask_open_template,
    ) -> None:
        self._open_docx = open_docx_func
        self._open_template = open_template_func

    # ---------------- copy helpers ---------------- #
    def import_docx_copy_only(self, *, parent: Any | None = None) -> ImportResult:
        try:
            src = self._open_docx(parent)
            if not src:
                return ImportResult(False, True, None, None, "cancelled")
            srcp = Path(src)
            if not srcp.exists() or srcp.suffix.lower() != ".docx":
                return ImportResult(False, False, str(srcp), None, "not_a_docx")
            inbox = get_inbox_dir()
            dest = _unique_dest(inbox, srcp.name)
            shutil.copy2(srcp, dest)
            try: logger.log("DocCreation", "ImportCopy", f"src={srcp}", f"dest={dest}")  # type: ignore
            except Exception: pass
            return ImportResult(True, False, str(srcp), str(dest), "copied")
        except Exception as exc:
            try: logger.log("DocCreation", "ImportCopyError", str(exc))  # type: ignore
            except Exception: pass
            return ImportResult(False, False, None, None, f"error:{type(exc).__name__}")

    def create_from_template(self, *, parent: Any | None = None) -> ImportResult:
        try:
            src = self._open_template(parent)
            if not src:
                return ImportResult(False, True, None, None, "cancelled")
            srcp = Path(src)
            if not srcp.exists() or srcp.suffix.lower() not in (".dotx", ".docx"):
                return ImportResult(False, False, str(srcp), None, "not_a_template")
            drafts = get_drafts_dir()
            dest_name = srcp.stem + ".docx"  # ensure .docx working copy
            dest = _unique_dest(drafts, dest_name)
            shutil.copy2(srcp, dest)
            try: logger.log("DocCreation", "TemplateCopy", f"src={srcp}", f"dest={dest}")  # type: ignore
            except Exception: pass
            return ImportResult(True, False, str(srcp), str(dest), "created")
        except Exception as exc:
            try: logger.log("DocCreation", "TemplateCopyError", str(exc))  # type: ignore
            except Exception: pass
            return ImportResult(False, False, None, None, f"error:{type(exc).__name__}")

    # ---------------- DB helpers ---------------- #
    def register_copied_docx_in_db(
        self,
        *,
        dest_path: str,
        created_by_user_id: Optional[int],
        default_doc_type: str,
        default_status: str,
        title: Optional[str],
        code: Optional[str],
        description: str = "",
    ) -> Optional[int]:
        try:
            from documentlifecycle.logic.repository.sqlite.document_repository_sqlite import DocumentRepositorySQLite  # type: ignore
            repo = DocumentRepositorySQLite()  # type: ignore[call-arg]
        except Exception:
            return None

        candidates = [
            ("create_from_file", dict(title=title or Path(dest_path).stem,
                                      doc_type=default_doc_type, user_id=created_by_user_id,
                                      src_file=dest_path, status=default_status,
                                      description=description, code=code)),
            ("create_basic_record", dict(title=title or Path(dest_path).stem,
                                         doc_type=default_doc_type, created_by=created_by_user_id,
                                         file_path=dest_path, status=default_status,
                                         description=description, code=code)),
            ("insert_imported", dict(title=title or Path(dest_path).stem,
                                     type=default_doc_type, created_by=created_by_user_id,
                                     path=dest_path, status=default_status,
                                     description=description, code=code)),
        ]
        for name, kwargs in candidates:
            try:
                fn = getattr(repo, name, None)
                if callable(fn):
                    new_id = fn(**kwargs)  # type: ignore[misc]
                    if isinstance(new_id, int):
                        try: logger.log("DocCreation", "DBRegister", f"id={new_id}", f"path={dest_path}")  # type: ignore
                        except Exception: pass
                        return new_id
            except Exception:
                continue
        return None

    def update_metadata(self, *, doc_id: int, title: str, code: Optional[str],
                        doc_type: str, description: str = "") -> bool:
        try:
            from documentlifecycle.logic.repository.sqlite.document_repository_sqlite import DocumentRepositorySQLite  # type: ignore
            repo = DocumentRepositorySQLite()  # type: ignore[call-arg]
            fn = getattr(repo, "update_metadata", None)
            if callable(fn):
                fn(doc_id=doc_id, title=title, code=code, doc_type=doc_type, description=description)  # type: ignore[misc]
                return True
        except Exception:
            pass
        return False

    # ---------------- defaults ---------------- #
    def derive_defaults_from_path(self, dest_path: str, *, for_new: bool) -> MetadataDefaults:
        """
        Build defaults for metadata dialog (code/title/type/description).
        Type is resolved from the TWO-LETTER token (EX->EXT, QM->QMH).
        """
        code, title, tt2 = parse_code_and_title_from_path(dest_path)
        dtype = from_two_letter_code(tt2).value
        return MetadataDefaults(title=title, code=code, doc_type=dtype, description="")
