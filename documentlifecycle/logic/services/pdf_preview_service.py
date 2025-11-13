"""
===============================================================================
PdfPreviewService – open temporary PDF previews and cleanup
-------------------------------------------------------------------------------
Behavior
    - Create a temp PDF (using the supplied DocxToPdfService) from a DOCX.
    - Open it with the system viewer.
    - On Windows, try to block until viewer closes (best effort).
    - Otherwise schedule deletion after a short delay (best effort).
===============================================================================
"""
from __future__ import annotations
import os
import sys
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from .docx_to_pdf_service import DocxToPdfService


class PdfPreviewService:
    """Manages temporary previews for DOCX files."""

    def __init__(self, docx_to_pdf: DocxToPdfService) -> None:
        self._docx2pdf = docx_to_pdf

    def open_docx_preview_and_cleanup(self, docx_path: Path, *, delete_after_seconds: int = 600) -> None:
        """Convert DOCX to temp PDF, open it, and cleanup later."""
        pdf = self._docx2pdf.convert_to_temp_pdf(docx_path)

        if sys.platform.startswith("win"):
            # Try to wait until the viewer closes using cmd start /WAIT (best effort)
            try:
                subprocess.run(["cmd", "/c", "start", "", "/WAIT", str(pdf)], check=False)
                self._safe_delete(pdf)
                return
            except Exception:
                pass

        # Non-Windows or failed wait: open and schedule deletion
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", str(pdf)])
            elif sys.platform.startswith("win"):
                os.startfile(str(pdf))  # type: ignore[arg-type]
            else:
                subprocess.Popen(["xdg-open", str(pdf)])
        except Exception:
            pass

        # delayed cleanup
        t = threading.Thread(target=self._delayed_delete, args=(pdf, delete_after_seconds), daemon=True)
        t.start()

    # ---- helpers ---- #
    def _delayed_delete(self, path: Path, delay: int) -> None:
        time.sleep(max(5, delay))
        self._safe_delete(path)

    def _safe_delete(self, path: Path) -> None:
        try:
            if path.exists():
                path.unlink(missing_ok=True)
                # remove temp dir if empty
                parent = path.parent
                if parent.is_dir() and not any(parent.iterdir()):
                    parent.rmdir()
        except Exception:
            pass
