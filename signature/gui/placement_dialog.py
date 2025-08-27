from __future__ import annotations
import io
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Tuple

from pypdf import PdfReader
from PIL import Image, ImageTk, ImageEnhance

from core.common.app_context import T
from ..models.signature_enums import LabelPosition
from ..models.signature_placement import SignaturePlacement
from ..models.label_offsets import LabelOffsets

# Präzise PDF-Vorschau
try:
    import pypdfium2 as pdfium  # type: ignore
except Exception:
    pdfium = None


def _hex_to_rgb(hexstr: str) -> Tuple[int, int, int]:
    s = (hexstr or "#000000").strip()
    if not s.startswith("#"):
        s = "#" + s
    if len(s) == 4:
        r = int(s[1] * 2, 16)
        g = int(s[2] * 2, 16)
        b = int(s[3] * 2, 16)
    else:
        r = int(s[1:3], 16)
        g = int(s[3:5], 16)
        b = int(s[5:7], 16)
    return (r, g, b)


class PlacementDialog(tk.Toplevel):
    """
    Präzises Platzieren:
      • Echte Seitenvorschau (pypdfium2)
      • Halbtransparente echte Signatur
      • Vereinfachte UI: Name oben/unten + EIN Offset, Datum oben/unten + EIN Offset
      • Links­bündige Ausrichtung von Signatur, Name, Datum

    Ergebnis:
      self.result = (SignaturePlacement, (name_pos, date_pos), LabelOffsets)
    """

    # kompakter: ~50–75 % der alten Größe
    CANVAS_MAX_W = 450
    CANVAS_MAX_H = 600
    PREVIEW_FONT = ("Segoe UI", 12, "bold")  # gut sichtbar („dick“)

    def __init__(
        self,
        parent: tk.Misc,
        pdf_path: str,
        default_placement: SignaturePlacement,
        default_name_pos: LabelPosition,
        default_date_pos: LabelPosition,
        default_offsets: LabelOffsets,
        *,
        signature_png: Optional[bytes] = None,
        show_name: bool = True,
        show_date: bool = True,
        label_name_text: Optional[str] = None,
        date_format: str = "%Y-%m-%d %H:%M",
        label_color_hex: str = "#000000",
    ) -> None:
        super().__init__(parent)
        self.title(T("core_signature.sign.place_title") or "Place Signature")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self._pdf_path = pdf_path
        self._reader = PdfReader(pdf_path)
        self._page_index = tk.IntVar(
            value=max(0, min(default_placement.page_index, len(self._reader.pages) - 1))
        )
        self._width = tk.DoubleVar(value=max(12.0, float(default_placement.target_width)))

        # reduzierte Label-UI
        self._name_pos = tk.StringVar(value=default_name_pos.value)
        self._date_pos = tk.StringVar(value=default_date_pos.value)
        self._name_offset = tk.DoubleVar(
            value=default_offsets.name_above if default_name_pos == LabelPosition.ABOVE else default_offsets.name_below
        )
        self._date_offset = tk.DoubleVar(
            value=default_offsets.date_above if default_date_pos == LabelPosition.ABOVE else default_offsets.date_below
        )
        self._x_offset = float(default_offsets.x_offset)

        self._show_name = bool(show_name)
        self._show_date = bool(show_date)
        self._label_name_text = (label_name_text or "").strip()  # sollte full_name sein
        self._date_format = date_format
        self._label_rgb = _hex_to_rgb(label_color_hex or "#000000")

        # Platzierung in PDF-pt (linke untere Ecke der Signatur)
        self._px = float(default_placement.x)
        self._py = float(default_placement.y)

        # Seitenverhältnis der Signatur
        self._sig_aspect = 0.3
        self._sig_tk: Optional[ImageTk.PhotoImage] = None
        self._sig_png = signature_png
        if signature_png:
            try:
                im = Image.open(io.BytesIO(signature_png)).convert("RGBA")
                if im.width > 0:
                    self._sig_aspect = im.height / im.width
            except Exception:
                pass

        # Transform
        self._scale = 1.0
        self._offset = (0.0, 0.0)
        self._bg_img_tk: Optional[ImageTk.PhotoImage] = None

        self.result: Optional[tuple[SignaturePlacement, tuple[LabelPosition, LabelPosition], LabelOffsets]] = None

        # ---------- UI
        top = ttk.Frame(self)
        top.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Kopfzeile mit Einstellungen + „Place & Sign“ rechts
        ctrl = ttk.Frame(top)
        ctrl.grid(row=0, column=0, sticky="ew")
        ctrl.columnconfigure(10, weight=1)  # Spacer

        ttk.Label(ctrl, text=T("core_signature.sign.page") or "Page").grid(row=0, column=0, sticky="w")
        self._page_spin = ttk.Spinbox(
            ctrl,
            from_=0,
            to=len(self._reader.pages) - 1,
            textvariable=self._page_index,
            width=4,
            command=self._on_page_change,
        )
        self._page_spin.grid(row=0, column=1, padx=(6, 12), sticky="w")

        ttk.Label(ctrl, text=T("core_signature.sign.width") or "Width (pt)").grid(row=0, column=2, sticky="w")
        w_entry = ttk.Entry(ctrl, textvariable=self._width, width=8)
        w_entry.grid(row=0, column=3, padx=(6, 12), sticky="w")
        w_entry.bind("<FocusOut>", lambda e: self._refresh_canvas())

        ttk.Label(ctrl, text=T("core_signature.name_pos") or "Name").grid(row=1, column=0, sticky="w", pady=(6, 0))
        cbn = ttk.Combobox(
            ctrl, textvariable=self._name_pos, values=[v.value for v in LabelPosition], state="readonly", width=10
        )
        cbn.grid(row=1, column=1, padx=(6, 12), sticky="w")
        cbn.bind("<<ComboboxSelected>>", lambda e: self._refresh_canvas())
        ttk.Label(ctrl, text="Offset (pt)").grid(row=1, column=2, sticky="w", pady=(6, 0))
        en = ttk.Entry(ctrl, textvariable=self._name_offset, width=8)
        en.grid(row=1, column=3, padx=(6, 12), sticky="w")
        en.bind("<FocusOut>", lambda e: self._refresh_canvas())

        ttk.Label(ctrl, text=T("core_signature.date_pos") or "Date").grid(row=2, column=0, sticky="w")
        cbd = ttk.Combobox(
            ctrl, textvariable=self._date_pos, values=[v.value for v in LabelPosition], state="readonly", width=10
        )
        cbd.grid(row=2, column=1, padx=(6, 12), sticky="w")
        cbd.bind("<<ComboboxSelected>>", lambda e: self._refresh_canvas())
        ttk.Label(ctrl, text="Offset (pt)").grid(row=2, column=2, sticky="w")
        ed = ttk.Entry(ctrl, textvariable=self._date_offset, width=8)
        ed.grid(row=2, column=3, padx=(6, 12), sticky="w")
        ed.bind("<FocusOut>", lambda e: self._refresh_canvas())

        # Spacer + „Place & Sign“ oben rechts
        ttk.Button(ctrl, text=T("core_signature.sign.confirm") or "Place & Sign", command=self._ok).grid(
            row=0, column=11, rowspan=3, sticky="e"
        )

        # Canvas
        self._canvas = tk.Canvas(
            top, width=self.CANVAS_MAX_W, height=self.CANVAS_MAX_H, bg="#f8f8f8", highlightthickness=1, highlightbackground="#888"
        )
        self._canvas.grid(row=1, column=0, pady=(8, 0))
        self._canvas.bind("<Button-1>", self._on_click)

        if pdfium is None:
            messagebox.showinfo(
                "Live-Vorschau",
                "Für die präzise Seitenvorschau bitte 'pypdfium2' installieren:\n\npip install pypdfium2",
                parent=self,
            )

        self._refresh_canvas()
        self._center_if_not_visible()

    # ---------------- Helper/Geom
    def _page_size(self) -> tuple[float, float]:
        page = self._reader.pages[int(self._page_index.get())]
        box = page.mediabox
        return float(box.width), float(box.height)

    def _canvas_from_pdf(self, x_pt: float, y_pt: float) -> tuple[float, float]:
        offx, offy = self._offset
        return offx + x_pt * self._scale, offy + (self._page_size()[1] - y_pt) * self._scale

    def _pdf_from_canvas(self, x_cv: float, y_cv: float) -> tuple[float, float]:
        offx, offy = self._offset
        pw, ph = self._page_size()
        x_pt = (x_cv - offx) / self._scale
        y_pt = ph - (y_cv - offy) / self._scale
        return x_pt, y_pt

    # ---------------- Render
    def _refresh_canvas(self):
        self._canvas.delete("all")

        pw, ph = self._page_size()
        sx = self.CANVAS_MAX_W / pw
        sy = self.CANVAS_MAX_H / ph
        self._scale = min(sx, sy)
        cw, ch = pw * self._scale, ph * self._scale
        offx = (self.CANVAS_MAX_W - cw) / 2
        offy = (self.CANVAS_MAX_H - ch) / 2
        self._offset = (offx, offy)

        # Echte Seite
        self._bg_img_tk = None
        if pdfium is not None:
            try:
                pdf = pdfium.PdfDocument(self._pdf_path)
                page = pdf[self._page_index.get()]
                try:
                    pil = page.render_topil(scale=self._scale)  # ältere Helper
                except Exception:
                    bm = page.render(scale=self._scale)  # neue API
                    pil = bm.to_pil()
                self._bg_img_tk = ImageTk.PhotoImage(pil)
                self._canvas.create_image(offx, offy, image=self._bg_img_tk, anchor="nw")
            except Exception:
                self._bg_img_tk = None

        if self._bg_img_tk is None:
            # Fallback: sauberer weißer Rahmen (ohne Zusatztexte)
            self._canvas.create_rectangle(offx, offy, offx + cw, offy + ch, fill="white", outline="#666")

        self._draw_signature_preview()
        self._draw_labels_preview()

    def _draw_signature_preview(self):
        """Halbtransparente echte Signatur, linksbündig an (px,py) mit Zielbreite."""
        px, py = self._px, self._py
        w_pt = max(12.0, float(self._width.get()))
        h_pt = w_pt * (self._sig_aspect if self._sig_aspect > 0 else 0.3)

        pw, ph = self._page_size()
        w_pt = min(w_pt, max(12.0, pw - 2.0))
        h_pt = min(h_pt, max(6.0, ph - 2.0))
        px = max(0.0, min(px, pw - w_pt))
        py = max(0.0, min(py, ph - h_pt))

        x0, y0 = self._canvas_from_pdf(px, py + h_pt)  # top-left

        if self._sig_png:
            try:
                sig = Image.open(io.BytesIO(self._sig_png)).convert("RGBA")
                sig = sig.resize((max(1, int(w_pt * self._scale)), max(1, int(h_pt * self._scale))), Image.LANCZOS)
                # ~60% Alpha
                r, g, b, a = sig.split()
                a = ImageEnhance.Brightness(a).enhance(0.6)
                sig = Image.merge("RGBA", (r, g, b, a))
                self._sig_tk = ImageTk.PhotoImage(sig)
                self._canvas.create_image(x0, y0, image=self._sig_tk, anchor="nw")
                return
            except Exception:
                self._sig_tk = None

        # Platzhalter (falls kein PNG)
        x1, y1 = self._canvas_from_pdf(px + w_pt, py)
        self._canvas.create_rectangle(x0, y0, x1, y1, fill="#D6EBFF", outline="#0A84FF", width=2)

    def _draw_labels_preview(self):
        """Nur *eine* gut sichtbare (fette) Vorschau von Name/Datum, linksbündig."""
        pw, ph = self._page_size()
        px, py = self._px, self._py
        w_pt = max(12.0, float(self._width.get()))
        h_pt = w_pt * (self._sig_aspect if self._sig_aspect > 0 else 0.3)
        w_pt = min(w_pt, max(12.0, pw - 2.0))
        h_pt = min(h_pt, max(6.0, ph - 2.0))
        px = max(0.0, min(px, pw - w_pt))
        py = max(0.0, min(py, ph - h_pt))

        left_pt = px + self._x_offset
        top_pt = py + h_pt
        bottom_pt = py

        col = "#%02X%02X%02X" % self._label_rgb

        if self._show_name and self._label_name_text:
            y_pt = (top_pt + float(self._name_offset.get())) if LabelPosition(self._name_pos.get()) == LabelPosition.ABOVE \
                   else (bottom_pt - float(self._name_offset.get()))
            nx, ny = self._canvas_from_pdf(left_pt, y_pt)
            # linksbündig (startet an left_pt)
            self._canvas.create_text(nx, ny, text=self._label_name_text, anchor="sw", fill=col, font=self.PREVIEW_FONT)

        if self._show_date:
            import datetime as _dt
            date_text = _dt.datetime.now().strftime(self._date_format)
            y_pt = (top_pt + float(self._date_offset.get())) if LabelPosition(self._date_pos.get()) == LabelPosition.ABOVE \
                   else (bottom_pt - float(self._date_offset.get()))
            dx, dy = self._canvas_from_pdf(left_pt, y_pt)
            self._canvas.create_text(dx, dy, text=date_text, anchor="sw", fill=col, font=self.PREVIEW_FONT)

    # ---------------- Events
    def _on_click(self, e):
        x_pt, y_pt = self._pdf_from_canvas(e.x, e.y)
        pw, ph = self._page_size()
        w_pt = max(12.0, float(self._width.get()))
        h_pt = w_pt * (self._sig_aspect if self._sig_aspect > 0 else 0.3)
        x_pt = max(0.0, min(x_pt, pw - w_pt))
        y_pt = max(0.0, min(y_pt, ph - h_pt))
        self._px, self._py = x_pt, y_pt
        self._refresh_canvas()

    def _on_page_change(self):
        try:
            idx = int(self._page_index.get())
            if idx < 0:
                self._page_index.set(0)
            if idx > len(self._reader.pages) - 1:
                self._page_index.set(len(self._reader.pages) - 1)
        except Exception:
            self._page_index.set(0)
        self._refresh_canvas()
        self._center_if_not_visible()

    def _center_if_not_visible(self):
        pw, ph = self._page_size()
        w = max(12.0, float(self._width.get()))
        h = w * (self._sig_aspect if self._sig_aspect > 0 else 0.3)
        w = min(w, max(12.0, pw - 2.0))
        h = min(h, max(6.0, ph - 2.0))
        x0_cv, y0_cv = self._canvas_from_pdf(self._px, self._py + h)
        x1_cv, y1_cv = self._canvas_from_pdf(self._px + w, self._py)
        in_view = (
            0 <= x0_cv <= self.CANVAS_MAX_W
            and 0 <= x1_cv <= self.CANVAS_MAX_W
            and 0 <= y0_cv <= self.CANVAS_MAX_H
            and 0 <= y1_cv <= self.CANVAS_MAX_H
        )
        if not in_view:
            self._px = (pw - w) / 2.0
            self._py = (ph - h) / 2.0
            self._refresh_canvas()

    def _ok(self):
        placement = SignaturePlacement(
            page_index=int(self._page_index.get()),
            x=float(self._px),
            y=float(self._py),
            target_width=max(12.0, float(self._width.get())),
        )
        name_pos = LabelPosition(self._name_pos.get())
        date_pos = LabelPosition(self._date_pos.get())
        # Aus einem Offset je Richtung wieder vollständige Offsets bauen
        offsets = LabelOffsets(
            name_above=(float(self._name_offset.get()) if name_pos == LabelPosition.ABOVE else 6.0),
            name_below=(float(self._name_offset.get()) if name_pos == LabelPosition.BELOW else 12.0),
            date_above=(float(self._date_offset.get()) if date_pos == LabelPosition.ABOVE else 18.0),
            date_below=(float(self._date_offset.get()) if date_pos == LabelPosition.BELOW else 24.0),
            x_offset=self._x_offset,
        )
        self.result = (placement, (name_pos, date_pos), offsets)
        self.destroy()
