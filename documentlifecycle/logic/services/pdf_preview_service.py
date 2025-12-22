"""
===============================================================================
PdfPreviewService – open previews without blocking the Tk mainloop
-------------------------------------------------------------------------------
Behavior
- DOCX preview: convert → open viewer → do NOT wait.
- Temp cleanup: best-effort in Hintergrund-Thread + atexit Fallback.
- Öffnet systemtypisch:
    * Windows: os.startfile(path)
    * macOS:  Popen(['open', path])
    * Linux:  Popen(['xdg-open', path])

No UI code here; exceptions wandern zum Caller/Controller.
===============================================================================
"""
from __future__ import annotations

import atexit
import os
import sys
import time
import threading
import tempfile
import subprocess
from pathlib import Path
from typing import Optional

from documentlifecycle.logic.services.docx_to_pdf_service import DocxToPdfService


class PdfPreviewService:
    def __init__(self, docx_to_pdf: Optional[DocxToPdfService] = None) -> None:
        self._docx2pdf = docx_to_pdf or DocxToPdfService()
        self._tmp_dir = Path(tempfile.gettempdir()) / "dlc_previews"
        self._tmp_dir.mkdir(parents=True, exist_ok=True)
        atexit.register(self._cleanup_old_previews)

    # ---------- public -------------------------------------------------------
    def open_docx_preview_and_cleanup(self, docx_path: Path) -> None:
        """Convert DOCX to temp PDF and open it without blocking the GUI."""
        def worker() -> None:
            pdf_path = self._docx2pdf.convert_to_temp_pdf(docx_path, target_dir=self._tmp_dir)
            self._open_non_blocking(pdf_path)
            # optional: verzögertes Aufräumen, wenn Viewer geschlossen wurde
            self._delayed_best_effort_delete(pdf_path, delay_sec=60 * 30)  # 30 min

        threading.Thread(target=worker, daemon=True).start()

    # ---------- helpers ------------------------------------------------------
    def _open_non_blocking(self, path: Path) -> None:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def _delayed_best_effort_delete(self, path: Path, *, delay_sec: int) -> None:
        """Delete the file later (no blocking). Ignores any failure."""
        def _delete_job() -> None:
            try:
                time.sleep(delay_sec)
                if path.exists():
                    path.unlink(missing_ok=True)  # type: ignore[call-arg]
            except Exception:
                pass
        threading.Thread(target=_delete_job, daemon=True).start()

    def _cleanup_old_previews(self) -> None:
        """Best-effort cleanup on interpreter exit (ignore errors)."""
        try:
            for p in self._tmp_dir.glob("*.pdf"):
                try:
                    if p.stat().st_mtime < (time.time() - 24 * 3600):  # älter als 24h
                        p.unlink(missing_ok=True)  # type: ignore[call-arg]
                except Exception:
                    continue
        except Exception:
            pass
