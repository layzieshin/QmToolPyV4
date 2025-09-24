"""
DOC/PDF conversion helpers (hardened).

Strategies in order:
1) Windows + docx2pdf (preferred; uses MS Word if installed).
2) Windows + direct Word COM automation via pywin32 (no docx2pdf needed).
3) LibreOffice (soffice/libreoffice) headless conversion (cross-platform).
4) Pass-through for already-PDF inputs (no conversion, just normalize/copy).

Returns the path to the generated/normalized PDF or None on failure.
No UI operations here; callers decide how to report errors.

Commercial note: pywin32/docx2pdf are permissively licensed; LibreOffice is an external tool.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Optional


# ---------- small utilities -------------------------------------------------

def _ensure_parent_dir(path: str) -> None:
    """Create parent directory of target path if missing."""
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)


def _norm_paths(src_path: str, dst_path: Optional[str]) -> tuple[str, str]:
    """Normalize input/output paths and compute default destination if needed."""
    src = os.path.abspath(src_path)
    if dst_path:
        dst = os.path.abspath(dst_path)
    else:
        base, _ = os.path.splitext(src)
        dst = base + ".pdf"
    return src, dst


# ---------- strategy 0: pass-through for PDFs -------------------------------

def _strategy_pdf_passthrough(src: str, dst: str) -> Optional[str]:
    """
    If the source is already a PDF, we don't convert. We either:
    - return src if dst == src, or
    - copy to dst and return dst.
    """
    if not src.lower().endswith(".pdf"):
        return None
    _ensure_parent_dir(dst)
    try:
        if os.path.abspath(src) == os.path.abspath(dst):
            # Nothing to do
            return src if os.path.isfile(src) else None
        shutil.copyfile(src, dst)
        return dst if os.path.isfile(dst) else None
    except Exception:
        return None


# ---------- strategy 1: docx2pdf (Windows) ----------------------------------

def _strategy_docx2pdf(src: str, dst: str) -> Optional[str]:
    """
    Use docx2pdf on Windows. Works best if MS Word is installed.
    """
    if os.name != "nt":
        return None
    if not src.lower().endswith(".docx"):
        return None
    try:
        from docx2pdf import convert  # type: ignore
    except Exception:
        return None  # package not present

    try:
        _ensure_parent_dir(dst)
        convert(src, dst)
        return dst if os.path.isfile(dst) else None
    except Exception:
        return None


# ---------- strategy 2: Word COM via pywin32 (Windows) ----------------------

def _strategy_word_com(src: str, dst: str) -> Optional[str]:
    """
    Use Microsoft Word via COM automation (pywin32) to export PDF.
    Very reliable if Word is installed; does not require docx2pdf.
    """
    if os.name != "nt":
        return None
    if not src.lower().endswith(".docx"):
        return None

    try:
        import pythoncom  # type: ignore
        import win32com.client as win32  # type: ignore
    except Exception:
        return None  # pywin32 not installed

    _ensure_parent_dir(dst)

    # WinWord export format constant
    wdExportFormatPDF = 17
    app = None
    doc = None
    try:
        pythoncom.CoInitialize()
        app = win32.DispatchEx("Word.Application")
        app.Visible = False
        doc = app.Documents.Open(src, ReadOnly=True)
        doc.ExportAsFixedFormat(OutputFileName=dst, ExportFormat=wdExportFormatPDF)
        return dst if os.path.isfile(dst) else None
    except Exception:
        return None
    finally:
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
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


# ---------- strategy 3: LibreOffice (any OS) --------------------------------

def _strategy_libreoffice(src: str, dst: str) -> Optional[str]:
    """
    Use LibreOffice in headless mode to convert to PDF.
    """
    try:
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if not soffice:
            return None

        out_dir = os.path.dirname(dst) or os.getcwd()
        _ensure_parent_dir(dst)

        cmd = [soffice, "--headless", "--convert-to", "pdf", "--outdir", out_dir, src]
        proc = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        generated = os.path.join(out_dir, os.path.splitext(os.path.basename(src))[0] + ".pdf")

        if proc.returncode == 0 and os.path.isfile(generated):
            if os.path.abspath(generated) != os.path.abspath(dst):
                try:
                    os.replace(generated, dst)
                except Exception:
                    shutil.copyfile(generated, dst)
            return dst if os.path.isfile(dst) else None
        return None
    except Exception:
        return None


# ---------- public API ------------------------------------------------------

def convert_to_pdf(src_path: str, dst_path: Optional[str] = None) -> Optional[str]:
    """
    Convert an input document to PDF and return the resulting path or None.

    Behavior:
    - If the source is already a PDF, we pass it through (optionally copying/renaming).
    - Otherwise we try (in order): docx2pdf (Windows) -> Word COM (Windows) -> LibreOffice.
    - Function is intentionally silent on failure; callers decide how to notify users.

    Parameters
    ----------
    src_path : str
        Source document path (DOCX/PDF; others may work via LibreOffice).
    dst_path : Optional[str]
        Desired output PDF path. If omitted, '<src_basename>.pdf' next to src is used.
    """
    src, dst = _norm_paths(src_path, dst_path)

    if not os.path.isfile(src):
        return None

    # Try pass-through first (already-PDF case)
    out = _strategy_pdf_passthrough(src, dst)
    if out:
        return out

    # Try in robust order
    for fn in (_strategy_docx2pdf, _strategy_word_com, _strategy_libreoffice):
        out = fn(src, dst)
        if out and os.path.isfile(out):
            return out

    # No strategy succeeded
    return None
