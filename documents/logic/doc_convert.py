"""
DOC/PDF conversion helpers.

- Prefer docx2pdf on Windows (uses Word if installed).
- Fallback to LibreOffice (soffice) if available.
- Returns True/False on success; does not raise for common failures.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Optional


def convert_to_pdf(src_path: str, dst_path: Optional[str] = None) -> Optional[str]:
    """
    Convert an input document to PDF. Currently optimized for DOCX.
    Returns the path to the generated PDF or None on failure.
    """
    src = os.path.abspath(src_path)
    if not os.path.isfile(src):
        return None

    if not dst_path:
        base, _ = os.path.splitext(src)
        dst_path = base + ".pdf"

    # Strategy 1: Windows + docx2pdf (fastest & best fidelity if Word is installed)
    if os.name == "nt" and src.lower().endswith(".docx"):
        try:
            # import lazily to avoid hard dependency
            from docx2pdf import convert  # type: ignore
            out_dir = os.path.dirname(dst_path)
            os.makedirs(out_dir, exist_ok=True)
            convert(src, dst_path)
            return dst_path if os.path.isfile(dst_path) else None
        except Exception:
            pass

    # Strategy 2: LibreOffice (cross-platform)
    try:
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if soffice:
            out_dir = os.path.dirname(dst_path)
            os.makedirs(out_dir, exist_ok=True)
            cmd = [
                soffice, "--headless", "--convert-to", "pdf", "--outdir", out_dir, src
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            generated = os.path.join(out_dir, os.path.splitext(os.path.basename(src))[0] + ".pdf")
            if os.path.isfile(generated):
                if os.path.abspath(generated) != os.path.abspath(dst_path):
                    try:
                        os.replace(generated, dst_path)
                    except Exception:
                        shutil.copyfile(generated, dst_path)
                return dst_path
    except Exception:
        pass

    return None
