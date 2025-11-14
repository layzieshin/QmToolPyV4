"""
===============================================================================
DocumentStorageService – filesystem layout for documents (code/revision)
-------------------------------------------------------------------------------
Rules:
- One root directory for all documents (configurable via adapters/settings).
- For each document code (Kennung) there is a directory:
      <root>/<code>/
- For each draft iteration (revision) there is a subdirectory:
      <root>/<code>/rev_<NNN>/
- The working files are standardized:
      document.docx  (draft/edit phase)
      document.pdf   (after draft is completed / released)
- New drafts always work on DOCX. Later phases may produce PDF. If a document
  is rejected back to editing, continue from the last available DOCX revision.
===============================================================================
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional


def _default_root() -> Path:
    # Fallback if no adapter is available.
    return Path("./storage/documents").resolve()


def _get_root_from_adapters() -> Path:
    """
    Try to resolve the root folder from adapters/settings if present.
    We try multiple options to avoid hard dependency.
    """
    # 1) Try explicit adapter (recommended place)
    try:
        from documentlifecycle.logic.adapters.storage_paths import get_documents_root_dir  # type: ignore
        p = get_documents_root_dir()
        if p:
            return Path(p).resolve()
    except Exception:
        pass

    # 2) Try generic settings manager (optional)
    try:
        from core.settings.logic.settings_manager import SettingsManager  # type: ignore
        sm = SettingsManager()
        basedir = sm.get("documentlifecycle.documents_root")  # e.g. user-configured folder
        if basedir:
            return Path(basedir).resolve()
    except Exception:
        pass

    return _default_root()


class DocumentStorageService:
    """
    Encapsulates filesystem rules & operations for document storage.
    """

    DOCX_NAME = "document.docx"
    PDF_NAME = "document.pdf"

    def __init__(self) -> None:
        self._root = _get_root_from_adapters()
        self._root.mkdir(parents=True, exist_ok=True)

    # ---------------- path helpers ---------------- #
    def code_dir(self, code: str) -> Path:
        d = self._root / code
        d.mkdir(parents=True, exist_ok=True)
        return d

    def revision_dir(self, code: str, revision: int) -> Path:
        cdir = self.code_dir(code)
        rdir = cdir / f"rev_{revision:03d}"
        rdir.mkdir(parents=True, exist_ok=True)
        return rdir

    def docx_path(self, code: str, revision: int) -> Path:
        return self.revision_dir(code, revision) / self.DOCX_NAME

    def pdf_path(self, code: str, revision: int) -> Path:
        return self.revision_dir(code, revision) / self.PDF_NAME

    # ---------------- discovery ---------------- #
    def latest_revision(self, code: str) -> int:
        cdir = self.code_dir(code)
        max_rev = -1
        for child in cdir.iterdir():
            if child.is_dir() and child.name.startswith("rev_"):
                try:
                    num = int(child.name.split("_", 1)[1])
                    if num > max_rev:
                        max_rev = num
                except Exception:
                    continue
        return max_rev if max_rev >= 0 else 0

    def next_revision(self, code: str) -> int:
        return self.latest_revision(code) + 1

    def find_latest_docx(self, code: str) -> Optional[Path]:
        rev = self.latest_revision(code)
        while rev >= 0:
            p = self.docx_path(code, rev)
            if p.exists():
                return p
            rev -= 1
        return None

    # ---------------- write ops ---------------- #
    def place_imported_docx(self, tmp_file: str, *, code: str, revision: int) -> Path:
        """
        Move the temporary imported file to its canonical DOCX location.
        Overwrites an existing docx for that revision (rare).
        """
        dst = self.docx_path(code, revision)
        dst.parent.mkdir(parents=True, exist_ok=True)
        Path(tmp_file).replace(dst)
        return dst

    def ensure_docx_exists(self, *, code: str, revision: int) -> Optional[Path]:
        """
        Ensure a DOCX exists for the given code/revision. If not present,
        clone from the latest older docx (if available). Returns the path or None.
        """
        p = self.docx_path(code, revision)
        if p.exists():
            return p
        # try to copy from older docx as base
        src = self.find_latest_docx(code)
        if src:
            p.parent.mkdir(parents=True, exist_ok=True)
            data = src.read_bytes()
            p.write_bytes(data)
            return p
        return None
