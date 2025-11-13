"""
===============================================================================
EditingService – Open DOCX in default editor (derive path if needed)
-------------------------------------------------------------------------------
Behavior
    - If DB already points to a DOCX: open it.
    - If DB points to PDF (or nothing), try to derive a DOCX via
      DocumentStorageService(code, revision) and update DB file_path.
    - If no DOCX can be determined, raise with a clear message.

Collaborators
    - DocumentRepositorySQLite
    - DocumentStorageService (optional, only if available)
===============================================================================
"""
from __future__ import annotations

import os
import sys
import subprocess
from typing import Optional

from documentlifecycle.logic.repository.sqlite.document_repository_sqlite import DocumentRepositorySQLite

try:
    from documentlifecycle.logic.services.document_storage_service import DocumentStorageService  # type: ignore
except Exception:  # pragma: no cover
    DocumentStorageService = None  # type: ignore

try:
    from core.common.app_context import T  # type: ignore
except Exception:  # pragma: no cover
    def T(_key: str) -> str: return ""


def _open_with_os(path: str) -> None:
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


class EditingService:
    """Editing use case for DOCX paths."""

    def __init__(self) -> None:
        self._repo = DocumentRepositorySQLite()
        self._store = DocumentStorageService() if DocumentStorageService else None

    def open_for_edit(self, *, document_id: int) -> None:
        doc = self._repo.get_by_id(document_id)
        if not doc:
            raise RuntimeError(T("documentlifecycle.errors.unexpected") or "Unexpected error.")

        path = (getattr(doc, "file_path", "") or "").strip()
        if path.lower().endswith(".docx"):
            _open_with_os(path)
            return

        # try to derive DOCX if we only have PDF
        if self._store:
            code = getattr(doc, "code", None) or self._repo.get_code_for_id(document_id)
            rev = getattr(doc, "revision", 0) or 0
            if code:
                docx_path = self._store.ensure_docx_exists(code=code, revision=rev)
                if docx_path:
                    try:
                        self._repo.update_file_path(doc_id=document_id, new_path=str(docx_path))
                    except Exception:
                        pass
                    _open_with_os(str(docx_path))
                    return

        raise RuntimeError(T("documentlifecycle.edit.only_docx") or
                           "Editing requires an available DOCX file.")
