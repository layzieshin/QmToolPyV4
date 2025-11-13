"""
===============================================================================
PrintingService – Controlled-copy printing with watermark and usage counter
-------------------------------------------------------------------------------
Rules
    - Only allowed for RELEASED/PUBLISHED/ARCHIVED.
    - Ensure PDF source (convert DOCX ad-hoc if needed).
    - Create watermarked copy ("kontrollierte Kopie").
    - Send to printer (platform-specific), then increment print counter.

Collaborators
    - DocumentRepositorySQLite
    - DocumentPrintRepositorySQLite
    - DocxToPdfService
    - PdfWatermarkService
===============================================================================
"""
from __future__ import annotations

import os
import sys
import time
import subprocess
from pathlib import Path
from typing import Optional, Protocol, Any

try:
    from core.common.app_context import T  # type: ignore
except Exception:  # pragma: no cover
    def T(_key: str) -> str: return ""

from documentlifecycle.logic.repository.sqlite.document_repository_sqlite import DocumentRepositorySQLite
from documentlifecycle.logic.repository.sqlite.print_repository_sqlite import DocumentPrintRepositorySQLite
from documentlifecycle.logic.services.docx_to_pdf_service import DocxToPdfService
from documentlifecycle.logic.services.pdf_watermark_service import PdfWatermarkService


class _UserProvider(Protocol):
    def current_user_id(self) -> Optional[int]: ...
    def get_current_user(self) -> Any: ...


class PrintingService:
    """Printing use case with watermark and per-user print counter."""

    def __init__(self) -> None:
        self._repo = DocumentRepositorySQLite()
        self._prints = DocumentPrintRepositorySQLite()
        self._docx2pdf = DocxToPdfService()
        self._wm = PdfWatermarkService()

    def print_controlled_copy(self, *, document_id: int, user_provider: Optional[_UserProvider]) -> None:
        # 1) Status guard
        doc = self._repo.get_by_id(document_id)
        st_val = getattr(doc, "status", None)
        status = (getattr(st_val, "value", st_val) or "").upper()
        if status not in ("RELEASED", "PUBLISHED", "ARCHIVED"):
            raise RuntimeError(T("documentlifecycle.print.only_released") or
                               "Printing allowed only for released/archived documents.")

        # 2) Ensure we have a source PDF
        src = (self._repo.get_file_path(document_id) or "").strip()
        if not src:
            raise RuntimeError(T("documentlifecycle.errors.missing_file") or "No file path set.")

        if src.lower().endswith(".pdf"):
            pdf_src = Path(src)
        elif src.lower().endswith(".docx"):
            pdf_src = self._docx2pdf.convert_to_temp_pdf(Path(src))
        else:
            raise RuntimeError(T("documentlifecycle.errors.unsupported") or "Unsupported file format.")

        # 3) Create watermarked copy
        wm_text = T("documentlifecycle.watermark.controlled_copy") or "kontrollierte Kopie"
        watermarked = self._wm.create_watermarked_copy(pdf_src, watermark_text=wm_text)

        # 4) Send to printer (fallback: open viewer)
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(watermarked), "print")  # type: ignore[arg-type]
                time.sleep(2.0)
            elif sys.platform == "darwin":
                subprocess.Popen(["lp", str(watermarked)])
            else:
                subprocess.Popen(["lp", str(watermarked)])
        except Exception:
            # best effort: open in viewer so the user can print manually
            if sys.platform.startswith("win"):
                os.startfile(str(watermarked))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(watermarked)])
            else:
                subprocess.Popen(["xdg-open", str(watermarked)])

        # 5) Counter++
        uid: Optional[int] = None
        try:
            if user_provider and hasattr(user_provider, "current_user_id"):
                uid = user_provider.current_user_id()
            elif user_provider and hasattr(user_provider, "get_current_user"):
                u = user_provider.get_current_user()
                uid = getattr(u, "id", None)
        except Exception:
            uid = None

        try:
            self._prints.increment_count(document_id=document_id, user_id=uid)
        except Exception:
            # Counter failure must never block printing
            pass
