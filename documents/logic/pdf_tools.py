"""
PDF utilities:
- Add text watermark ("Controlled Copy" or "OBSOLETE").
- Stamp PNG signature onto a PDF (bottom-right).

Uses PyMuPDF if available; otherwise returns False to indicate no stamping was done.
"""

from __future__ import annotations

from typing import Optional
import os
import tempfile
import shutil

try:
    import fitz  # PyMuPDF
    _HAVE_FITZ = True
except Exception:
    _HAVE_FITZ = False


def add_text_watermark(in_pdf: str, out_pdf: str, text: str, opacity: float = 0.2) -> bool:
    if not _HAVE_FITZ:
        return False
    doc = fitz.open(in_pdf)
    for page in doc:
        rect = page.rect
        page.insert_textbox(
            rect, text,
            fontsize=72, rotate=45, align=fitz.TEXT_ALIGN_CENTER,
            overlay=True, color=(0, 0, 0), fill_opacity=opacity
        )
    doc.save(out_pdf)
    doc.close()
    return True


def stamp_signature(in_pdf: str, out_pdf: str, png_bytes: bytes, label: Optional[str] = None) -> bool:
    if not _HAVE_FITZ:
        return False
    # Save PNG to temp
    with tempfile.TemporaryDirectory() as td:
        sig_path = os.path.join(td, "sig.png")
        with open(sig_path, "wb") as f:
            f.write(png_bytes)
        doc = fitz.open(in_pdf)
        for page in doc:
            rect = page.rect
            # place at bottom-right with margin
            box_w, box_h = rect.width * 0.25, rect.height * 0.12
            x1 = rect.x1 - box_w - 36
            y1 = rect.y1 - box_h - 36
            img_rect = fitz.Rect(x1, y1, x1 + box_w, y1 + box_h)
            page.insert_image(img_rect, filename=sig_path, keep_proportion=True, overlay=True)
            if label:
                page.insert_text((x1, y1 - 6), label, fontsize=8, overlay=True)
        doc.save(out_pdf)
        doc.close()
    return True


def make_controlled_copy(in_pdf: str, out_pdf: str, watermark_text: str) -> bool:
    # Try to watermark. If failed, fallback to a raw copy.
    ok = add_text_watermark(in_pdf, out_pdf, watermark_text, opacity=0.15)
    if not ok:
        shutil.copyfile(in_pdf, out_pdf)
    return True
