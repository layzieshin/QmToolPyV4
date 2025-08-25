from __future__ import annotations
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from core.common.app_context import AppContext, T
from core.settings.logic.settings_manager import SettingsManager
from ..logic.signature_service import SignatureService
from ..models.signature_placement import SignaturePlacement
from .placement_dialog import PlacementDialog
from .password_prompt_dialog import PasswordPromptDialog
from .signature_capture_dialog import SignatureCaptureDialog

class SignatureView(ttk.Frame):
    def __init__(self, parent: tk.Misc, *,
                 settings_manager: SettingsManager = None,
                 sm: SettingsManager = None, logger=None, password_verifier=None) -> None:
        super().__init__(parent)
        self._sm = settings_manager or sm
        self._service = SignatureService(settings_manager=self._sm, logger=logger, password_verifier=password_verifier)

        self.columnconfigure(0, weight=1)
        ttk.Label(self, text=T("core_signature.title") or "PDF Signature",
                  font=("Segoe UI", 16, "bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))
        ttk.Label(self, text=T("core_signature.info") or "Select a PDF and place your signature.")\
            .grid(row=1, column=0, sticky="w", padx=12, pady=(0, 8))
        ttk.Button(self, text=T("common.choose_file") or "Choose PDF…", command=self._choose)\
            .grid(row=2, column=0, sticky="w", padx=12, pady=(0, 12))

    def _ensure_signature(self) -> bool:
        user = getattr(AppContext, "current_user", None)
        uid = getattr(user, "id", None)
        if not uid:
            messagebox.showerror(title=T("common.error") or "Error",
                                 message=T("core_signature.no_user") or "No logged-in user.", parent=self)
            return False
        if self._service.load_user_signature_png(uid) is None:
            if messagebox.askyesno(title=T("core_signature.nosig.title") or "No signature on file",
                                   message=T("core_signature.nosig.text") or "Do you want to create a signature now?",
                                   parent=self):
                dlg = SignatureCaptureDialog(self, service=self._service); self.wait_window(dlg)
                return self._service.load_user_signature_png(uid) is not None
            else:
                return False
        return True

    def _choose(self):
        path = filedialog.askopenfilename(parent=self, title=T("core_signature.pick") or "Choose PDF",
                                          filetypes=[("PDF", "*.pdf")])
        if not path: return
        if not self._ensure_signature(): return

        cfg = self._service.load_config()
        default_place = SignaturePlacement()
        user = getattr(AppContext, "current_user", None)
        uid = getattr(user, "id", None)
        full_name = (getattr(user, "full_name", None) or getattr(user, "name", None) or getattr(user, "username", None))
        sig_png = self._service.load_user_signature_png(uid) if uid else None

        pd = PlacementDialog(self,
            pdf_path=path,
            default_placement=default_place,
            default_name_pos=cfg.name_position,
            default_date_pos=cfg.date_position,
            default_offsets=cfg.label_offsets,
            signature_png=sig_png,
            show_name=bool(cfg.embed_name),
            show_date=bool(cfg.embed_date),
            label_name_text=full_name,
            date_format=cfg.date_format,
            label_color_hex=cfg.label_color,
        )
        self.wait_window(pd)
        if not pd.result: return
        placement, (name_pos, date_pos), offsets = pd.result

        if self._service.is_password_required():
            attempts = 0
            while attempts < 3:
                dlg = PasswordPromptDialog(self); self.wait_window(dlg)
                if not dlg.password:
                    messagebox.showerror(title=T("common.error") or "Error",
                                         message=T("core_signature.password.required") or "Password required.", parent=self)
                    return
                if self._service.verify_password(uid, dlg.password): break
                attempts += 1
                messagebox.showerror(title=T("common.error") or "Error",
                                     message=T("core_signature.password.wrong") or "Wrong password.", parent=self)
            if attempts >= 3: return

        try:
            out = self._service.sign_pdf(
                input_path=path, placement=placement, reason="manual",
                enforce_label_positions=(name_pos, date_pos),
                override_label_offsets=offsets
            )
            messagebox.showinfo(title=T("common.done") or "Done",
                                message=(T("core_signature.done") or "Signed file created:\n") + out, parent=self)
        except Exception as ex:
            messagebox.showerror(title=T("common.error") or "Error", message=str(ex), parent=self)
