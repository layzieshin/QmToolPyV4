from __future__ import annotations
from dataclasses import dataclass
from io import BytesIO
from typing import Optional, Tuple
from pypdf import PdfReader, PdfWriter
from PIL import Image
# ReportLab für Overlay (OSS, kommerziell nutzbar)
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from ..models.signature_enums import LabelPosition
from ..models.signature_placement import SignaturePlacement
from ..models.label_offsets import LabelOffsets

@dataclass
class RenderLabels:
    name_text: Optional[str]
    date_text: Optional[str]
    name_pos: LabelPosition
    date_pos: LabelPosition
    date_format: str
    offsets: LabelOffsets
    color_rgb: Tuple[int,int,int] = (0, 0, 0)  # NEW

class PdfSigner:
    @staticmethod
    def _make_overlay(page_w: float, page_h: float,
                      png_signature: bytes,
                      placement: SignaturePlacement,
                      labels: Optional[RenderLabels]) -> bytes:
        """
        Erzeugt eine PDF-Seite gleicher Größe, die die Signatur (PNG mit Alpha) sowie
        optional Name/Datum in gewünschter Farbe enthält. Wird anschließend über die Zielseite gemerged.
        """
        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=(page_w, page_h))
        # Signatur platzieren
        sig = Image.open(BytesIO(png_signature)).convert("RGBA")
        # Höhe aus Zielbreite ermitteln
        aspect = sig.height / sig.width if sig.width > 0 else 0.3
        target_w = float(placement.target_width)
        target_h = max(6.0, target_w * aspect)

        # ReportLab-Koordinaten: (0,0) unten links
        c.drawImage(ImageReader(sig), placement.x, placement.y, width=target_w, height=target_h, mask='auto')

        # Labels
        if labels:
            r, g, b = labels.color_rgb
            c.setFillColorRGB(r/255.0, g/255.0, b/255.0)
            x_left = placement.x + labels.offsets.x_offset
            y_top = placement.y + target_h
            y_bottom = placement.y

            if labels.name_text:
                y = (y_top + labels.offsets.name_above) if labels.name_pos == LabelPosition.ABOVE \
                    else (y_bottom - labels.offsets.name_below)
                c.setFont("Helvetica-Bold", 10)
                c.drawString(x_left, y, labels.name_text)

            if labels.date_text:
                y = (y_top + labels.offsets.date_above) if labels.date_pos == LabelPosition.ABOVE \
                    else (y_bottom - labels.offsets.date_below)
                c.setFont("Helvetica-Bold", 10)
                c.drawString(x_left, y, labels.date_text)

        c.save()
        return buf.getvalue()

    @staticmethod
    def sign_pdf(*, input_path: str, output_path: str,
                 png_signature: bytes,
                 placement: SignaturePlacement,
                 labels: Optional[RenderLabels]) -> None:
        reader = PdfReader(input_path)
        writer = PdfWriter()
        n = len(reader.pages)
        for i in range(n):
            page = reader.pages[i]
            if i == placement.page_index:
                box = page.mediabox
                w, h = float(box.width), float(box.height)
                overlay_pdf = PdfSigner._make_overlay(w, h, png_signature, placement, labels)
                # Overlay importieren und mergen
                overlay_reader = PdfReader(BytesIO(overlay_pdf))
                overlay_page = overlay_reader.pages[0]
                page.merge_page(overlay_page)
            writer.add_page(page)
        with open(output_path, "wb") as f:
            writer.write(f)
