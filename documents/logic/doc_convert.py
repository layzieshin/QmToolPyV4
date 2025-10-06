"""
DOC/PDF conversion helpers with markup suppression for Word documents.

Strategies (in order):
1) Windows + Word COM (preferred for .docx)  -> controls markup visibility; no tracked changes/comments in PDF
2) Windows + docx2pdf                        -> fallback if COM not available
3) LibreOffice headless                      -> cross-platform fallback (tries to disable comments)
4) Pass-through for already-PDF inputs

Returns absolute path to created/normalized PDF or None on failure.
No UI imports or message boxes here.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

# ------------------------------- utils -------------------------------------


def _is_windows() -> bool:
    return os.name == "nt"


def _abspath(p: str) -> str:
    return str(Path(p).expanduser().resolve())


def _ensure_outdir(dst: str) -> None:
    Path(os.path.dirname(dst) or ".").mkdir(parents=True, exist_ok=True)


def _copy_pdf_passthrough(src: str, dst: str) -> Optional[str]:
    """If src is already a PDF, just normalize/copy to dst."""
    if not str(src).lower().endswith(".pdf"):
        return None
    _ensure_outdir(dst)
    if os.path.abspath(src) == os.path.abspath(dst):
        return src
    shutil.copyfile(src, dst)
    return dst


# ------------------------------ strategy 1 ---------------------------------
# Windows COM Automation with Word – we can suppress markup reliably


def _strategy_word_com(src: str, dst: str) -> Optional[str]:
    """
    Convert DOCX to PDF via Word COM Automation while hiding revisions/comments.
    Requires: Windows + pywin32 + Microsoft Word installed.
    """
    if not (_is_windows() and str(src).lower().endswith((".doc", ".docx"))):
        return None

    try:
        import win32com.client  # type: ignore
        from win32com.client import constants  # type: ignore
    except Exception:
        return None  # pywin32 not installed → try next strategy

    src = _abspath(src)
    dst = _abspath(dst)
    _ensure_outdir(dst)

    # Word constants (guarded for older Word versions)
    wdExportFormatPDF = getattr(constants, "wdExportFormatPDF", 17)
    wdExportOptimizeForPrint = getattr(constants, "wdExportOptimizeForPrint", 0)
    wdExportAllDocument = getattr(constants, "wdExportAllDocument", 0)
    wdExportDocumentContent = getattr(constants, "wdExportDocumentContent", 0)
    wdExportCreateHeadingBookmarks = getattr(constants, "wdExportCreateHeadingBookmarks", 1)
    wdRevisionsViewFinal = getattr(constants, "wdRevisionsViewFinal", 0)

    app = None
    doc = None
    try:
        app = win32com.client.DispatchEx("Word.Application")
        app.Visible = False
        app.ScreenUpdating = False

        # Open as ReadOnly to avoid touching the source file
        doc = app.Documents.Open(src, ReadOnly=True)

        # --- CRUCIAL: Hide markups for export --------------------------------
        try:
            # Show the "Final" view without markup and hide revisions/comments from View
            app.ActiveWindow.View.RevisionsView = wdRevisionsViewFinal
            app.ActiveWindow.View.ShowRevisionsAndComments = False
        except Exception:
            pass  # Not all Word versions expose both properties identically

        # Don't print revisions/comments
        try:
            doc.PrintRevisions = False
        except Exception:
            pass

        # In case "Track Changes" is on, we do NOT accept them – we only export without showing them.

        # Export → PDF (no markup visible)
        # We use ExportAsFixedFormat for better control than SaveAs2 for PDF.
        doc.ExportAsFixedFormat(
            OutputFileName=dst,
            ExportFormat=wdExportFormatPDF,
            OpenAfterExport=False,
            OptimizeFor=wdExportOptimizeForPrint,
            Range=wdExportAllDocument,
            From=1,
            To=1,
            Item=wdExportDocumentContent,
            IncludeDocProps=True,
            KeepIRM=True,
            CreateBookmarks=wdExportCreateHeadingBookmarks,
            DocStructureTags=True,
            BitmapMissingFonts=True,
            UseISO19005_1=False,
        )

        return dst if os.path.isfile(dst) else None

    except Exception:
        return None
    finally:
        # proper cleanup is vital; COM objects may keep files locked
        try:
            if doc is not None:
                doc.Close(False)
        except Exception:
            pass
        try:
            if app is not None:
                app.Quit()
        except Exception:
            pass


# ------------------------------ strategy 2 ---------------------------------
# docx2pdf (internally uses Word on Windows; less control over markup)

def _strategy_docx2pdf(src: str, dst: str) -> Optional[str]:
    if not (_is_windows() and str(src).lower().endswith((".doc", ".docx"))):
        return None
    try:
        from docx2pdf import convert  # type: ignore
    except Exception:
        return None

    src = _abspath(src)
    dst = _abspath(dst)
    _ensure_outdir(dst)

    # docx2pdf writes into a directory; we convert to a temp dir then move
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            convert(src, tmpdir)  # may use Word behind the scenes
        except Exception:
            return None

        # find produced PDF
        produced = None
        for p in Path(tmpdir).glob("*.pdf"):
            produced = str(p.resolve())
            break
        if not produced:
            # some Word installs name the PDF after the doc – try to compute it
            pdf_guess = str(Path(tmpdir) / (Path(src).stem + ".pdf"))
            if os.path.isfile(pdf_guess):
                produced = pdf_guess

        if not produced:
            return None

        shutil.move(produced, dst)
        return dst if os.path.isfile(dst) else None


# ------------------------------ strategy 3 ---------------------------------
# LibreOffice headless

def _strategy_libreoffice(src: str, dst: str) -> Optional[str]:
    # Cross-platform fallback using soffice/libreoffice
    if not str(src).lower().endswith((".docx", ".doc")):
        return None

    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None

    src = _abspath(src)
    dst = _abspath(dst)
    _ensure_outdir(dst)

    outdir = str(Path(dst).parent.resolve())

    # Filter options: try to disable exporting comments/notes
    # The options string for writer_pdf_Export is comma-separated key=value pairs.
    # Common keys: ExportBookmarks=true|false, ExportNotes=false
    # NOTE: Option names vary by LO version; we try a set that commonly works.
    filter_opts = "ExportBookmarks=true,ExportNotes=false"

    cmd = [
        soffice,
        "--headless",
        f"--convert-to",
        f"pdf:writer_pdf_Export:{filter_opts}",
        "--outdir",
        outdir,
        src,
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception:
        return None

    produced = str(Path(outdir) / (Path(src).stem + ".pdf"))
    if not os.path.isfile(produced):
        # LO sometimes drops the filter options → retry without them once
        try:
            subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf", "--outdir", outdir, src],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception:
            return None

    produced = str(Path(outdir) / (Path(src).stem + ".pdf"))
    if not os.path.isfile(produced):
        return None

    # move/rename to requested dst if different
    if os.path.abspath(produced) != os.path.abspath(dst):
        shutil.move(produced, dst)
    return dst if os.path.isfile(dst) else None


# ------------------------------ public API ---------------------------------


def convert_to_pdf(src: str, dst: str) -> Optional[str]:
    """
    Convert a document (DOC/DOCX/PDF) to PDF.

    For DOC/DOCX on Windows we prefer COM Automation to ensure NO markup is visible.
    Returns the path to the created PDF or None on failure.
    """
    if not src or not dst:
        return None

    src = _abspath(src)
    dst = _abspath(dst)

    # Fast path: passthrough for existing PDF
    out = _copy_pdf_passthrough(src, dst)
    if out:
        return out

    # Strategy 1: Word COM with markup suppression (preferred)
    out = _strategy_word_com(src, dst)
    if out:
        return out

    # Strategy 2: docx2pdf (fallback on Windows)
    out = _strategy_docx2pdf(src, dst)
    if out:
        return out

    # Strategy 3: LibreOffice headless (cross-platform fallback)
    out = _strategy_libreoffice(src, dst)
    if out:
        return out

    return None
