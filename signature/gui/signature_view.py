from __future__ import annotations
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from core.common.app_context import AppContext, T
from ..logic.signature_service import SignatureService
from ..models.signature_placement import SignaturePlacement
from ..models.signature_enums import LabelPosition
from .placement_dialog import PlacementDialog
from .password_prompt_dialog import PasswordPromptDialog
from .signature_capture_dialog import SignatureCaptureDialog


class SignatureView(ttk.Frame):
    """
    Haupt-View zum Signieren:
      • PDF auswählen
      • Platzieren (Live-Preview-Dialog)
      • Signieren

    Robuste Guards:
      - self._pdf_path existiert immer (StringVar)
      - Passwort-Policy wird beachtet
      - Kein Crash, wenn keine Signatur gespeichert ist: Abfrage zum Aufzeichnen
    """

    def __init__(self, parent, *, settings_manager=None, sm=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._sm = settings_manager or sm
        self._service = SignatureService(settings_manager=self._sm)
        self._pdf_path = tk.StringVar(value="")  # <-- fehlte vorher
        self._make_ui()

    # ------------------------------------------------------------------ UI
    def _make_ui(self) -> None:
        row = ttk.Frame(self)
        row.grid(row=0, column=0, sticky="ew", padx=12, pady=10)
        row.columnconfigure(0, weight=1)

        ttk.Entry(row, textvariable=self._pdf_path).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(row, text=T("core_signature.sign.browse") or "Choose PDF…",
                   command=self._browse).grid(row=0, column=1, sticky="e")
        ttk.Button(row, text=T("core_signature.sign.open_capture") or "Create signature…",
                   command=self._capture_if_needed).grid(row=0, column=2, padx=(6, 0))

        ttk.Button(self, text=T("core_signature.sign.place_btn") or "Place & Sign",
                   command=self._choose).grid(row=1, column=0, sticky="e", padx=12, pady=(0, 12))

    def _browse(self) -> None:
        p = filedialog.askopenfilename(parent=self,
                                       filetypes=[("PDF", "*.pdf")],
                                       title=T("core_signature.sign.choose_pdf") or "Choose PDF")
        if p:
            self._pdf_path.set(p)

    def _capture_if_needed(self) -> None:
        """Erlaubt manuell eine Signatur zu erstellen/zu ersetzen."""
        dlg = SignatureCaptureDialog(self, service=self._service)
        self.wait_window(dlg)

    # ------------------------------------------------------------------ Signing flow
    def _choose(self) -> None:
        """
        Öffnet den Platzierungsdialog und signiert danach die PDF.
        Seit dem Update liefert der Dialog 4 Werte:
          (placement, (name_pos, date_pos), offsets, (name_fs, date_fs))
        Für Rückwärtskompatibilität akzeptieren wir auch 3 Werte.
        """
        if not self._pdf_path.get():
            messagebox.showinfo(T("common.info") or "Info",
                                T("core_signature.sign.choose_pdf_first") or "Please choose a PDF first.",
                                parent=self)
            return

        # Prüfe, ob eine Signatur gespeichert ist, sonst freundlich fragen
        uid = getattr(AppContext.current_user, "id", None)
        sig = self._service.load_user_signature_png(uid) if uid else None
        if not sig:
            if not messagebox.askyesno(
                T("common.question") or "Question",
                T("core_signature.sign.no_sig_q") or "No signature stored. Create one now?",
                parent=self,
            ):
                return
            self._capture_if_needed()
            sig = self._service.load_user_signature_png(uid)
            if not sig:
                # User hat abgebrochen
                return

        # Platzierung
        cfg = self._service.load_config()
        full_name = (getattr(AppContext.current_user, "full_name", None)
                     or getattr(AppContext.current_user, "name", None)
                     or getattr(AppContext.current_user, "username", None) or "")

        dlg = PlacementDialog(
            self,
            pdf_path=self._pdf_path.get(),
            default_placement=SignaturePlacement(page_index=0, x=72.0, y=72.0, target_width=max(120.0, 180.0)),
            default_name_pos=cfg.name_position,
            default_date_pos=cfg.date_position,
            default_offsets=cfg.label_offsets,
            signature_png=sig,
            show_name=bool(cfg.embed_name),
            show_date=bool(cfg.embed_date),
            label_name_text=full_name,
            date_format=cfg.date_format,
            label_color_hex=cfg.label_color,
            name_font_size=cfg.name_font_size,
            date_font_size=cfg.date_font_size,
        )
        self.wait_window(dlg)
        if not dlg.result:
            return

        # robust auspacken (3 oder 4 Rückgabewerte)
        font_sizes = (cfg.name_font_size, cfg.date_font_size)
        try:
            if len(dlg.result) == 4:
                placement, (name_pos, date_pos), offsets, font_sizes = dlg.result
            else:
                placement, (name_pos, date_pos), offsets = dlg.result
        except Exception:
            placement, (name_pos, date_pos), offsets = dlg.result[:3]

        # Passwort-Policy
        pwd = None
        if self._service.is_password_required():
            attempts = 0
            while attempts < 3:
                pd = PasswordPromptDialog(self)
                self.wait_window(pd)
                if not pd.password:
                    return
                if self._service.verify_password(uid, pd.password):
                    pwd = pd.password
                    break
                attempts += 1
                messagebox.showerror(title=T("common.error") or "Error",
                                     message=T("core_signature.password.wrong") or "Wrong password.",
                                     parent=self)
            if attempts >= 3:
                return

        # Signieren
        try:
            out = self._service.sign_pdf(
                input_path=self._pdf_path.get(),
                placement=placement,
                enforce_label_positions=(name_pos, date_pos),
                override_label_offsets=offsets,
                override_font_sizes=font_sizes,
                reason="manual",
            )
            messagebox.showinfo(T("common.done") or "Done",
                                (T("core_signature.done") or "Signed file created:\n") + out,
                                parent=self)
        except Exception as ex:
            messagebox.showerror(T("common.error") or "Error", str(ex), parent=self)
