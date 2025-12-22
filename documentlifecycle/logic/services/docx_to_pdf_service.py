"""
===============================================================================
DocxToPdfService – convert DOCX to PDF (Windows Word or LibreOffice fallback)
-------------------------------------------------------------------------------
Strategy
    - On Windows: try Microsoft Word COM automation (win32com.client).
    - Else: try LibreOffice 'soffice --headless --convert-to pdf'.
    - Returns the path to an output PDF (temp file) or raises an Exception.

Contract (important!)
    convert_to_temp_pdf(docx_path, *, target_dir=None) -> Path

    - Callers MAY pass target_dir to control where the resulting PDF is created.
    - The returned Path points to the created PDF.
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
    """Convert a DOCX file into a PDF file (prefer Word on Windows, else LibreOffice)."""

    def convert_to_temp_pdf(self, docx_path: Path, *, target_dir: Optional[Path] = None) -> Path:
        """Convert a DOCX file into a PDF.

        Contract (Variant A)
        --------------------
        - Callers may specify a *target_dir* to control where the resulting PDF
          is created (e.g. PdfPreviewService wants a stable preview folder).
        - The method returns the absolute path to the created PDF.
        - No UI interaction happens here (pure service).

        Parameters
        ----------
        docx_path:
            Path to the source .docx file.
        target_dir:
            Optional output directory.
            If None, a new temporary directory is created for this conversion.

        Returns
        -------
        Path
            The path to the created PDF file.
        """
        docx_path = Path(docx_path).resolve()
        if not docx_path.exists():
            raise FileNotFoundError(str(docx_path))

        # Decide output directory (Variant A: caller controls directory)
        if target_dir is None:
            out_dir = Path(tempfile.mkdtemp(prefix="dlc_docx2pdf_"))
        else:
            out_dir = Path(target_dir).expanduser().resolve()
            out_dir.mkdir(parents=True, exist_ok=True)

        out_pdf = self._unique_pdf_path(out_dir, docx_path.stem)

        # Windows-first strategy: Word COM -> docx2pdf -> soffice
        if sys.platform.startswith("win"):
            if self._try_word_com(docx_path, out_pdf):
                return out_pdf
            if self._try_docx2pdf(docx_path, out_pdf):
                return out_pdf

        # Fallback: LibreOffice/soffice can only control the directory, not the file name.
        # To avoid overwriting an existing file, we convert into a private temp directory
        # and then move the result into our chosen target path.
        if target_dir is None:
            # out_dir is already unique, so it's safe to convert directly there.
            if self._try_soffice(docx_path, out_dir) and out_pdf.exists():
                return out_pdf
        else:
            work_dir = Path(tempfile.mkdtemp(prefix="dlc_soffice_"))
            try:
                if self._try_soffice(docx_path, work_dir):
                    generated = work_dir / (docx_path.stem + ".pdf")
                    if generated.exists():
                        shutil.move(str(generated), str(out_pdf))
                        return out_pdf
            finally:
                shutil.rmtree(work_dir, ignore_errors=True)

        raise RuntimeError(f"Could not convert DOCX to PDF: {docx_path}")

    @staticmethod
    def _unique_pdf_path(out_dir: Path, stem: str) -> Path:
        """Create a unique PDF file path inside *out_dir* without overwriting.

        Example:
            NAME.pdf, NAME (2).pdf, NAME (3).pdf, ...
        """
        candidate = out_dir / f"{stem}.pdf"
        i = 2
        while candidate.exists():
            candidate = out_dir / f"{stem} ({i}).pdf"
            i += 1
        return candidate

    # ---- Word COM ---- #
    def _try_word_com(self, docx: Path, out_pdf: Path) -> bool:
        if not sys.platform.startswith("win"):
            return False
        try:
            import win32com.client  # type: ignore
        except Exception:
            return False

        word = None
        doc = None
        try:
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            doc = word.Documents.Open(str(docx))
            # 17 = wdFormatPDF
            doc.SaveAs(str(out_pdf), FileFormat=17)
            return out_pdf.exists()
        except Exception:
            return False
        finally:
            try:
                if doc is not None:
                    doc.Close(False)
            except Exception:
                pass
            try:
                if word is not None:
                    word.Quit()
            except Exception:
                pass

    # ---- docx2pdf (optional) ---- #
    def _try_docx2pdf(self, docx: Path, out_pdf: Path) -> bool:
        try:
            from docx2pdf import convert  # type: ignore
        except Exception:
            return False

        try:
            tmp_dir = out_pdf.parent
            tmp_dir.mkdir(parents=True, exist_ok=True)
            # docx2pdf writes into the output directory using the input stem
            convert(str(docx), str(tmp_dir))
            expected = tmp_dir / (docx.stem + ".pdf")
            if expected.exists():
                if expected.resolve() != out_pdf.resolve():
                    shutil.move(str(expected), str(out_pdf))
                return out_pdf.exists()
            return False
        except Exception:
            return False

    # ---- LibreOffice ---- #
    def _try_soffice(self, docx: Path, out_dir: Path) -> bool:
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if not soffice:
            return False
        try:
            subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(docx)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            return False
