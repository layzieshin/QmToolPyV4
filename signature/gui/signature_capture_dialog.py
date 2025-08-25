# signature/gui/signature_capture_dialog.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import List, Tuple, Optional
from core.common.app_context import AppContext, T
from ..logic.signature_service import SignatureService
from .password_prompt_dialog import PasswordPromptDialog


class SignatureCaptureDialog(tk.Toplevel):
    """
    Smooth signature capture (Tk canvas with spline smoothing), adjustable stroke width,
    optional import of an existing PNG/GIF. Saves encrypted per user via SignatureService.

    IMPORTANT:
    - We DO NOT embed name/date into the PNG here to avoid duplicate labels later.
    - Overwrite requires confirmation + password (up to 3 attempts).
    """
    CANVAS_W = 800
    CANVAS_H = 220

    def __init__(self, parent: tk.Misc, *, service: SignatureService) -> None:
        super().__init__(parent)
        self.title(T("core_signature.capture.title") or "Create Signature")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self._service = service
        self._strokes: List[List[Tuple[int, int]]] = []
        self._current: List[Tuple[int, int]] = []
        self._imported_image: Optional[str] = None

        self.columnconfigure(0, weight=1)

        # Toolbar
        bar = ttk.Frame(self)
        bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        ttk.Label(bar, text=T("core_signature.stroke_width") or "Stroke width").pack(side="left")
        self.stroke_var = tk.IntVar(value=self._service.load_config().stroke_width)
        ttk.Scale(bar, from_=1, to=10, variable=self.stroke_var, orient="horizontal", length=160).pack(
            side="left", padx=(6, 12)
        )
        ttk.Button(bar, text=T("common.clear") or "Clear", command=self._clear).pack(side="left")
        ttk.Button(bar, text=T("common.import") or "Import PNG/GIF", command=self._import).pack(side="left", padx=(6, 0))

        # Canvas
        self.canvas = tk.Canvas(
            self, width=self.CANVAS_W, height=self.CANVAS_H, bg="white",
            highlightthickness=1, highlightbackground="#888"
        )
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=10, pady=4)
        self.canvas.bind("<ButtonPress-1>", self._on_down)
        self.canvas.bind("<B1-Motion>", self._on_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_up)

        # Footer
        btns = ttk.Frame(self)
        btns.grid(row=2, column=0, sticky="e", padx=10, pady=(4, 10))
        ttk.Button(btns, text=T("common.cancel") or "Cancel", command=self._cancel).pack(side="right", padx=(6, 0))
        ttk.Button(btns, text=T("common.save") or "Save", command=self._save).pack(side="right")

    # Canvas handlers
    def _on_down(self, e):
        self._current = [(e.x, e.y)]
        self._line = self.canvas.create_line(
            e.x, e.y, e.x + 1, e.y + 1,
            fill="black",
            width=self.stroke_var.get(),
            capstyle="round",
            smooth=True,
            splinesteps=24
        )

    def _on_move(self, e):
        if self._current:
            self._current.append((e.x, e.y))
            # Update line coordinates
            self.canvas.coords(self._line, *sum(self._current, ()))

    def _on_up(self, e):
        if self._current:
            self._strokes.append(self._current)
            self._current = []

    # Actions
    def _clear(self):
        self.canvas.delete("all")
        self._strokes.clear()
        self._current = []

    def _import(self):
        p = filedialog.askopenfilename(
            parent=self,
            title=T("core_signature.import.title") or "Import signature image",
            filetypes=[("Images", "*.png *.gif")]
        )
        if p:
            self._imported_image = p
            self.canvas.delete("all")
            self._strokes.clear()
            self.canvas.create_text(
                self.CANVAS_W // 2, self.CANVAS_H // 2,
                text=T("core_signature.import.loaded") or "Image loaded (will be stored).",
                fill="black"
            )

    def _cancel(self):
        self.destroy()

    def _save(self):
        user = getattr(AppContext, "current_user", None)
        uid = getattr(user, "id", None)
        if not uid:
            messagebox.showerror(
                title="Error",
                message=T("core_signature.no_user") or "No logged-in user.",
                parent=self
            )
            return

        # Build PNG (NO name/date embedding here)
        if self._imported_image:
            with open(self._imported_image, "rb") as f:
                png_bytes = f.read()
        else:
            png_bytes = self._service.render_png_from_strokes(
                strokes=self._strokes,
                size=(self.CANVAS_W, self.CANVAS_H),
                stroke_width=max(1, int(self.stroke_var.get())),
                name_text=None,   # <- keep None to avoid duplicate labels
                date_text=None,
            )

        # Overwrite confirmation + password (up to 3 attempts)
        existing = self._service.load_user_signature_png(uid)
        if existing is not None:
            if not messagebox.askyesno(
                title=T("core_signature.overwrite.title") or "Overwrite signature?",
                message=T("core_signature.overwrite.text") or "A signature already exists. Overwrite?",
                parent=self
            ):
                return
            attempts = 0
            while attempts < 3:
                dlg = PasswordPromptDialog(self)
                self.wait_window(dlg)
                if not dlg.password:
                    return
                if self._service.verify_password(uid, dlg.password):
                    break
                attempts += 1
                messagebox.showerror(
                    title=T("common.error") or "Error",
                    message=T("core_signature.password.wrong") or "Wrong password.",
                    parent=self
                )
            if attempts >= 3:
                return

        self._service.save_user_signature_png(uid, png_bytes)
        messagebox.showinfo(
            title=T("common.saved") or "Saved",
            message=T("core_signature.saved") or "Signature saved.",
            parent=self
        )
        self.destroy()
