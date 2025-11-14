"""
===============================================================================
PdfWatermarkService – add "kontrollierte Kopie" watermark to each page
-------------------------------------------------------------------------------
Implementation
    - Uses reportlab (BSD) to render a watermark overlay for each page size.
    - Uses pypdf (MIT) to merge overlay onto all pages.
Licenses are permissive and OK for commercial distribution.
===============================================================================
"""
from __future__ import annotations
import tempfile
from pathlib import Path
from typing import Dict, Tuple

from reportlab.pdfgen import canvas  # type: ignore
from reportlab.lib.units import cm  # type: ignore
from reportlab.lib.colors import Color  # type: ignore
from pypdf import PdfReader, PdfWriter, PageObject  # type: ignore


class PdfWatermarkService:
    """Create watermarked copies of PDFs."""

    def __init__(self) -> None:
        # cache overlay PDFs per (width, height) in points
        self._cache: Dict[Tuple[float, float], Path] = {}

    def create_watermarked_copy(self, src_pdf: Path, *, watermark_text: str) -> Path:
        src_pdf = Path(src_pdf).resolve()
        if not src_pdf.exists():
            raise FileNotFoundError(str(src_pdf))

        reader = PdfReader(str(src_pdf))
        writer = PdfWriter()

        for page in reader.pages:
            w = float(page.mediabox.width)
            h = float(page.mediabox.height)
            overlay = self._get_overlay(w, h, watermark_text)
            overlay_reader = PdfReader(str(overlay))
            overlay_page = overlay_reader.pages[0]

            # merge overlay onto page
            # (pypdf <=3 uses PageObject.merge_page)
            page_out: PageObject = page
            page_out.merge_page(overlay_page)  # type: ignore[attr-defined]
            writer.add_page(page_out)

        tmp_out = Path(tempfile.mkstemp(prefix="dlc_wm_", suffix=".pdf")[1])
        with tmp_out.open("wb") as fh:
            writer.write(fh)
        return tmp_out

    # ---- helpers ---- #
    def _get_overlay(self, width_pt: float, height_pt: float, text: str) -> Path:
        key = (round(width_pt, 1), round(height_pt, 1))
        if key in self._cache:
            return self._cache[key]

        tmp_path = Path(tempfile.mkstemp(prefix="dlc_wm_ovl_", suffix=".pdf")[1])
        c = canvas.Canvas(str(tmp_path), pagesize=(width_pt, height_pt))

        # semi-transparent grey text diagonally across the page
        c.saveState()
        c.translate(width_pt / 2.0, height_pt / 2.0)
        c.rotate(45)
        # A subtle, semi-transparent color
        c.setFillColor(Color(0.2, 0.2, 0.2, alpha=0.15))
        c.setFont("Helvetica-Bold", 48)
        c.drawCentredString(0, 0, text)
        c.restoreState()

        # optional label in footer
        c.setFillColor(Color(0.1, 0.1, 0.1, alpha=0.25))
        c.setFont("Helvetica", 10)
        c.drawString(1.5 * cm, 1.5 * cm, text)

        c.showPage()
        c.save()

        self._cache[key] = tmp_path
        return tmp_path
