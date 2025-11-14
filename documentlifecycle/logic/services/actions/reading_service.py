"""
===============================================================================
ReadingService – Open document for reading (PDF directly, DOCX via temp preview)
-------------------------------------------------------------------------------
Responsibility
    - Decide how to open a document for reading.
    - DRAFT + DOCX -> create a temporary PDF preview, open it, and schedule cleanup.
    - PDF -> open directly.
    - DOCX (non-DRAFT) -> preview as best effort.

Collaborators
    - DocumentRepositorySQLite: fetch file path and status.
    - DocxToPdfService + PdfPreviewService: conversion & preview.
    - Facade: for user-visible messages (show_info/show_error), with fallback.

This service contains no GUI widgets; it only orchestrates I/O and raises
exceptions for the controller to surface, but also supports best-effort
facade messaging.
===============================================================================
"""
from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path
from typing import Protocol, Any, Optional

try:
    from core.common.app_context import T  # type: ignore
except Exception:  # pragma: no cover
    def T(_key: str) -> str: return ""

from documentlifecycle.logic.repository.sqlite.document_repository_sqlite import DocumentRepositorySQLite
from documentlifecycle.logic.services.docx_to_pdf_service import DocxToPdfService
from documentlifecycle.logic.services.pdf_preview_service import PdfPreviewService


class _FacadeLike(Protocol):
    def show_info(self, title: str, message: str) -> None: ...
    def show_error(self, title: str, message: str) -> None: ...


def _open_with_os(path: str) -> None:
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


class ReadingService:
    """Reading use case for the document lifecycle module."""

    def __init__(self) -> None:
        self._repo = DocumentRepositorySQLite()
        self._docx2pdf = DocxToPdfService()
        self._preview = PdfPreviewService(self._docx2pdf)

    def open_for_read(self, *, document_id: int, facade: Optional[_FacadeLike]) -> None:
        """
        Execute 'read' action for a given document id.

        Raises
        ------
        RuntimeError
            If required file/path is missing or an unexpected error occurs.
        """
        # Resolve file path
        file_path = (self._repo.get_file_path(document_id) or "").strip()
        if not file_path:
            raise RuntimeError(T("documentlifecycle.errors.missing_file") or "No file path set.")

        # Resolve status as uppercase string
        doc = self._repo.get_by_id(document_id)
        status_val = getattr(doc, "status", None)
        status = (getattr(status_val, "value", status_val) or "").upper()

        try:
            if file_path.lower().endswith(".pdf"):
                _open_with_os(file_path)
                return

            if file_path.lower().endswith(".docx"):
                # DRAFT -> preview; others -> preview as best effort
                self._preview.open_docx_preview_and_cleanup(Path(file_path))
                return

            # Unknown extension -> best effort open
            _open_with_os(file_path)

        except Exception as exc:
            # Prefer raising; controller will surface a message.
            raise RuntimeError(
                (T("documentlifecycle.errors.unexpected") or "Unexpected error") + f": {type(exc).__name__}"
            ) from exc
