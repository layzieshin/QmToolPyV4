"""
===============================================================================
DocumentCreationService – import/create flows + metadata defaults/persist
-------------------------------------------------------------------------------
Design goals (your project rules)
- Controllers must be anemic: one UI event -> one service call.
- Therefore, the full UI flows (dialogs + DB persist + UI refresh) live here:
    - run_import_flow(...)
    - run_create_from_template_flow(...)

Already existing low-level helpers remain:
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
    from core.qm_logging.logic.logger import logger  # type: ignore
except Exception:  # pragma: no cover
    class _NoopLogger:
        def log(self, *args, **kwargs) -> None: ...
    logger = _NoopLogger()  # type: ignore


# Optional i18n
try:
    from core.common.app_context import T  # type: ignore
except Exception:  # pragma: no cover
    def T(_key: str) -> str:
        return ""


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
    description: str


def _unique_dest(target_dir: Path, basename: str) -> Path:
    """
    Ensure we don't overwrite an existing file.
    Keep the original name and append ' (2)', ' (3)', ... before the extension.
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


def _resolve_user_id(user_provider: Any | None) -> Optional[int]:
    """Best-effort extraction of a user id from different provider shapes."""
    if user_provider is None:
        return None

    # Shape 1: current_user_id() -> int | None
    try:
        fn = getattr(user_provider, "current_user_id", None)
        if callable(fn):
            uid = fn()
            return int(uid) if uid is not None else None
    except Exception:
        pass

    # Shape 2: get_current_user().id
    try:
        fn = getattr(user_provider, "get_current_user", None)
        if callable(fn):
            u = fn()
            uid = getattr(u, "id", None)
            return int(uid) if uid is not None else None
    except Exception:
        pass

    return None


def _ui_show_info(view: Any, title: str, message: str) -> None:
    """UI helper: show info via view.show_info or tkinter fallback."""
    try:
        fn = getattr(view, "show_info", None)
        if callable(fn):
            fn(title, message)
            return
    except Exception:
        pass
    try:
        from tkinter import messagebox
        messagebox.showinfo(title=title, message=message, parent=view)
    except Exception:
        pass


def _ui_show_error(view: Any, title: str, message: str) -> None:
    """UI helper: show error via view.show_error or tkinter fallback."""
    try:
        fn = getattr(view, "show_error", None)
        if callable(fn):
            fn(title, message)
            return
    except Exception:
        pass
    try:
        from tkinter import messagebox
        messagebox.showerror(title=title, message=message, parent=view)
    except Exception:
        pass


def _ui_refresh_and_select(view: Any, doc_id: Optional[int]) -> None:
    """UI helper: refresh list + reselect document using view/facade surface."""
    try:
        fn = getattr(view, "load_document_list", None)
        if callable(fn):
            fn()
    except Exception:
        pass

    if isinstance(doc_id, int):
        try:
            fn = getattr(view, "on_select_document", None)
            if callable(fn):
                fn(doc_id)
        except Exception:
            pass


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
        """Select a .docx via dialog and copy it into the inbox folder."""
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
            try:
                logger.log("DocCreation", "ImportCopy", f"src={srcp}", f"dest={dest}")  # type: ignore
            except Exception:
                pass
            return ImportResult(True, False, str(srcp), str(dest), "copied")
        except Exception as exc:
            try:
                logger.log("DocCreation", "ImportCopyError", str(exc))  # type: ignore
            except Exception:
                pass
            return ImportResult(False, False, None, None, f"error:{type(exc).__name__}")

    def create_from_template(self, *, parent: Any | None = None) -> ImportResult:
        """Select a template and copy it into drafts as a working .docx."""
        try:
            src = self._open_template(parent)
            if not src:
                return ImportResult(False, True, None, None, "cancelled")
            srcp = Path(src)
            if not srcp.exists():
                return ImportResult(False, False, str(srcp), None, "not_found")

            drafts = get_drafts_dir()
            dest = _unique_dest(drafts, srcp.stem + ".docx")
            shutil.copy2(srcp, dest)
            try:
                logger.log("DocCreation", "TemplateCopy", f"src={srcp}", f"dest={dest}")  # type: ignore
            except Exception:
                pass
            return ImportResult(True, False, str(srcp), str(dest), "created")
        except Exception as exc:
            try:
                logger.log("DocCreation", "TemplateCopyError", str(exc))  # type: ignore
            except Exception:
                pass
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
        """Try to insert a document record using existing repository methods."""
        try:
            from documentlifecycle.logic.repository.sqlite.document_repository_sqlite import DocumentRepositorySQLite  # type: ignore
            repo = DocumentRepositorySQLite()  # type: ignore[call-arg]
        except Exception:
            return None

        # We try multiple signatures to remain compatible with your evolving repo.
        candidates = [
            ("create_from_file", dict(
                title=title or Path(dest_path).stem,
                doc_type=default_doc_type,
                user_id=created_by_user_id,
                src_file=dest_path,
                status=default_status,
                description=description,
                code=code,
            )),
            ("create_basic_record", dict(
                title=title or Path(dest_path).stem,
                doc_type=default_doc_type,
                created_by=created_by_user_id,
                file_path=dest_path,
                status=default_status,
                description=description,
                code=code,
            )),
            ("insert_imported", dict(
                title=title or Path(dest_path).stem,
                type=default_doc_type,
                created_by=created_by_user_id,
                path=dest_path,
                status=default_status,
                description=description,
                code=code,
            )),
        ]

        for name, kwargs in candidates:
            try:
                fn = getattr(repo, name, None)
                if callable(fn):
                    new_id = fn(**kwargs)  # type: ignore[misc]
                    if isinstance(new_id, int):
                        try:
                            logger.log("DocCreation", "DBRegister", f"id={new_id}", f"path={dest_path}")  # type: ignore
                        except Exception:
                            pass
                        return new_id
            except Exception:
                continue

        return None

    def update_metadata(self, *, doc_id: int, title: str, code: Optional[str],
                        doc_type: str, description: str = "") -> bool:
        """Update metadata fields if the repository exposes update_metadata()."""
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

    # -------------------------------------------------------------------------
    # FULL UI FLOWS (so controllers stay anemic)
    # -------------------------------------------------------------------------
    def run_import_flow(self, *, view: Any, user_provider: Any | None = None) -> None:
        """Full import flow: copy -> metadata dialog -> DB insert -> UI refresh."""
        from documentlifecycle.gui.dialogs.metadata_edit_dialog import MetadataEditDialog

        title = T("documentlifecycle.dialog.import.title") or "Import"
        parent = getattr(view, "winfo_toplevel", lambda: None)()

        copy_res = self.import_docx_copy_only(parent=parent)
        if copy_res.cancelled:
            _ui_show_info(view, title, T("documentlifecycle.dialog.import.cancelled") or "Import abgebrochen")
            return
        if not copy_res.ok or not copy_res.dest_path:
            _ui_show_error(view, title, f"{T('documentlifecycle.errors.unexpected') or 'Unerwarteter Fehler'}: {copy_res.message}")
            return

        defaults = self.derive_defaults_from_path(copy_res.dest_path, for_new=False)
        dlg = MetadataEditDialog(parent, title_text=title, initial={
            "title": defaults.title,
            "code": defaults.code,
            "doc_type": defaults.doc_type,
            "description": defaults.description,
        })
        edited = dlg.show_modal()
        if edited is None:
            _ui_show_info(view, title, T("documentlifecycle.dialog.import.cancelled") or "Import abgebrochen")
            return

        uid = _resolve_user_id(user_provider)
        new_id = self.register_copied_docx_in_db(
            dest_path=copy_res.dest_path,
            created_by_user_id=uid,
            default_doc_type=edited.get("doc_type") or "OTHER",
            default_status="IN_REVIEW",
            title=edited.get("title") or "",
            code=edited.get("code"),
            description=edited.get("description", "") or "",
        )

        _ui_refresh_and_select(view, new_id)
        _ui_show_info(view, title, (T("documentlifecycle.dialog.import.success") or "Datei importiert: {path}").format(path=copy_res.dest_path))

    def run_create_from_template_flow(self, *, view: Any, user_provider: Any | None = None) -> None:
        """Full create flow: copy template -> metadata dialog -> DB insert -> UI refresh."""
        from documentlifecycle.gui.dialogs.metadata_edit_dialog import MetadataEditDialog

        title = T("documentlifecycle.dialog.create.title") or "Neu"
        parent = getattr(view, "winfo_toplevel", lambda: None)()

        copy_res = self.create_from_template(parent=parent)
        if copy_res.cancelled:
            _ui_show_info(view, title, T("documentlifecycle.dialog.import.cancelled") or "Abgebrochen")
            return
        if not copy_res.ok or not copy_res.dest_path:
            _ui_show_error(view, title, f"{T('documentlifecycle.errors.unexpected') or 'Unerwarteter Fehler'}: {copy_res.message}")
            return

        defaults = self.derive_defaults_from_path(copy_res.dest_path, for_new=True)
        dlg = MetadataEditDialog(parent, title_text=title, initial={
            "title": defaults.title,
            "code": defaults.code,
            "doc_type": defaults.doc_type,
            "description": defaults.description,
        })
        edited = dlg.show_modal()
        if edited is None:
            _ui_show_info(view, title, T("documentlifecycle.dialog.import.cancelled") or "Abgebrochen")
            return

        uid = _resolve_user_id(user_provider)
        new_id = self.register_copied_docx_in_db(
            dest_path=copy_res.dest_path,
            created_by_user_id=uid,
            default_doc_type=edited.get("doc_type") or "OTHER",
            default_status="DRAFT",
            title=edited.get("title") or "",
            code=edited.get("code"),
            description=edited.get("description", "") or "",
        )

        _ui_refresh_and_select(view, new_id)
        _ui_show_info(view, title, (T("documentlifecycle.dialog.create.success") or "Neues Dokument erstellt: {path}").format(path=copy_res.dest_path))
