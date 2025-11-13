"""
===============================================================================
DocxToPdfService – convert DOCX to PDF (Windows Word or LibreOffice fallback)
-------------------------------------------------------------------------------
Strategy
    - On Windows: try Microsoft Word COM automation (win32com.client).
    - Else: try LibreOffice 'soffice --headless --convert-to pdf'.
    - Returns the path to an output PDF (temp file) or raises an Exception.
===============================================================================
"""
from __future__ import annotations
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional


class DocxToPdfService:
    """Convert a DOCX file into a temporary PDF file."""

    def convert_to_temp_pdf(self, docx_path: Path) -> Path:
        docx_path = Path(docx_path).resolve()
        if not docx_path.exists():
            raise FileNotFoundError(str(docx_path))

        tmp_dir = Path(tempfile.mkdtemp(prefix="dlc_docx2pdf_"))
        out_pdf = tmp_dir / (docx_path.stem + ".pdf")

        if sys.platform.startswith("win"):
            if self._try_word_com(docx_path, out_pdf):
                return out_pdf
            # optional: try docx2pdf if installed
            if self._try_docx2pdf(docx_path, out_pdf):
                return out_pdf

        # Fallback: try LibreOffice
        if self._try_soffice(docx_path, tmp_dir):
            guessed = tmp_dir / (docx_path.stem + ".pdf")
            if guessed.exists():
                guessed.replace(out_pdf)
                return out_pdf

        raise RuntimeError("DOCX->PDF conversion failed")

    # ---- Windows Word COM ---- #
    def _try_word_com(self, docx: Path, out_pdf: Path) -> bool:
        try:
            import win32com.client  # type: ignore
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            doc = word.Documents.Open(str(docx))
            # 17 = wdFormatPDF
            doc.SaveAs(str(out_pdf), FileFormat=17)
            doc.Close(False)
            word.Quit()
            return out_pdf.exists()
        except Exception:
            return False

    # ---- docx2pdf (optional) ---- #
    def _try_docx2pdf(self, docx: Path, out_pdf: Path) -> bool:
        try:
            from docx2pdf import convert  # type: ignore
            # docx2pdf writes to same folder; we convert to temp dir then move
            tmp_out_dir = out_pdf.parent
            convert(str(docx), str(tmp_out_dir))
            candidate = tmp_out_dir / (docx.stem + ".pdf")
            if candidate.exists():
                candidate.replace(out_pdf)
                return True
            return False
        except Exception:
            return False

    # ---- LibreOffice ---- #
    def _try_soffice(self, docx: Path, out_dir: Path) -> bool:
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if not soffice:
            return False
        try:
            # Convert into out_dir
            subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(docx)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return True
        except Exception:
            return False
