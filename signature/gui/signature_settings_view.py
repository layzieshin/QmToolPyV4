# signature/gui/signature_settings_view.py
from __future__ import annotations
import io
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Optional

from PIL import Image, ImageTk

from core.common.app_context import AppContext, T
from core.settings.logic.settings_manager import SettingsManager
from core.models.user import UserRole

from ..models.signature_config import SignatureConfig
from ..models.signature_enums import LabelPosition, AdminPasswordPolicy
from ..logic.signature_service import SignatureService
from .signature_capture_dialog import SignatureCaptureDialog
from .password_prompt_dialog import PasswordPromptDialog


# -------- Sichtbarkeit für Settings-Loader (siehe Punkt 3)
def settings_visibility_predicate() -> bool:
    """Nur anzeigen, wenn ein User eingeloggt ist."""
    return getattr(AppContext, "current_user", None) is not None


class SignatureSettingsView(ttk.Frame):
    """
    Settings-Tab für das Signature-Modul.
    - Akzeptiert 'settings_manager=' und 'sm='
    - Versteckt Admin-Block, wenn User nicht ADMIN
    - Bietet Management der Signature (Anzeigen/Import/Export/Löschen/Aufnehmen)
    """

    def __init__(self, parent: tk.Misc, *, settings_manager: SettingsManager | None = None,
                 sm: SettingsManager | None = None, **kwargs) -> None:
        super().__init__(parent)
        self._sm: SettingsManager | None = settings_manager or sm

        # --- Login-Gate: falls kein User -> nur Hinweis
        self._user = getattr(AppContext, "current_user", None)
        if self._user is None:
            ttk.Label(self, text=T("core_signature.settings.login_required")
                      or "Please log in to access signature settings.",
                      foreground="#a00").grid(row=0, column=0, padx=12, pady=12, sticky="w")
            return

        if self._sm is None:
            ttk.Label(self, text="SettingsManager missing (use 'settings_manager' or 'sm').")\
                .grid(row=0, column=0, padx=12, pady=12, sticky="w")
            return

        self._svc = SignatureService(settings_manager=self._sm)
        self._cfg = self._svc.load_config()
        self.columnconfigure(0, weight=1)

        # --- Titel
        ttk.Label(self, text=T("core_signature.settings.title") or "Signature Settings",
                  font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))

        # --- Einstellungen
        frm = ttk.Frame(self); frm.grid(row=1, column=0, sticky="nsew", padx=12, pady=8)

        ttk.Label(frm, text=T("core_signature.name_pos") or "Name position").grid(row=0, column=0, sticky="w")
        self._name_pos = tk.StringVar(value=self._cfg.name_position.value)
        ttk.Combobox(frm, textvariable=self._name_pos, values=[v.value for v in LabelPosition],
                     state="readonly", width=12).grid(row=0, column=1, sticky="w", padx=(6, 20))

        ttk.Label(frm, text=T("core_signature.date_pos") or "Date position").grid(row=0, column=2, sticky="w")
        self._date_pos = tk.StringVar(value=self._cfg.date_position.value)
        ttk.Combobox(frm, textvariable=self._date_pos, values=[v.value for v in LabelPosition],
                     state="readonly", width=12).grid(row=0, column=3, sticky="w", padx=(6, 20))

        ttk.Label(frm, text=T("core_signature.date_format") or "Date format (strftime)")\
            .grid(row=1, column=0, sticky="w", pady=(8, 0))
        self._date_fmt = tk.StringVar(value=self._cfg.date_format)
        ttk.Entry(frm, textvariable=self._date_fmt, width=16)\
            .grid(row=1, column=1, sticky="w", padx=(6, 20), pady=(8, 0))

        ttk.Label(frm, text="Label color (hex)").grid(row=1, column=2, sticky="w", pady=(8, 0))
        self._label_color = tk.StringVar(value=self._cfg.label_color or "#000000")
        ttk.Entry(frm, textvariable=self._label_color, width=12)\
            .grid(row=1, column=3, sticky="w", padx=(6, 20), pady=(8, 0))

        ttk.Label(frm, text="Name font size (pt)").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self._name_fs = tk.IntVar(value=self._cfg.name_font_size if self._cfg.name_font_size > 0 else 12)
        ttk.Spinbox(frm, from_=6, to=48, textvariable=self._name_fs, width=6)\
            .grid(row=2, column=1, sticky="w", padx=(6, 20), pady=(8, 0))

        ttk.Label(frm, text="Date font size (pt)").grid(row=2, column=2, sticky="w", pady=(8, 0))
        self._date_fs = tk.IntVar(value=self._cfg.date_font_size if self._cfg.date_font_size > 0 else 12)
        ttk.Spinbox(frm, from_=6, to=48, textvariable=self._date_fs, width=6)\
            .grid(row=2, column=3, sticky="w", padx=(6, 20), pady=(8, 0))

        # Sichtbarkeit Name/Datum
        self._embed_name = tk.BooleanVar(value=self._cfg.embed_name)
        self._embed_date = tk.BooleanVar(value=self._cfg.embed_date)
        ttk.Checkbutton(frm, text=T("core_signature.embed_name") or "Show name", variable=self._embed_name)\
            .grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Checkbutton(frm, text=T("core_signature.embed_date") or "Show date", variable=self._embed_date)\
            .grid(row=3, column=2, columnspan=2, sticky="w", pady=(8, 0))

        # --- Admin-Policy: nur für Admins
        show_admin = False
        try:
            role = getattr(self._user, "role", None)
            show_admin = (role == UserRole.ADMIN) or (getattr(role, "name", "").upper() == "ADMIN")
        except Exception:
            show_admin = False

        if show_admin:
            admf = ttk.LabelFrame(self, text=T("core_signature.admin.policy_title") or "Password policy (Admin)")
            admf.grid(row=2, column=0, sticky="ew", padx=12, pady=(8, 0))
            self._admin_policy = tk.StringVar(value=self._cfg.admin_password_policy.value)
            for i, (txt, val) in enumerate(((T("core_signature.admin.always") or "always", "always"),
                                            (T("core_signature.admin.never") or "never", "never"),
                                            (T("core_signature.admin.user") or "user-specific", "user_specific"))):
                ttk.Radiobutton(admf, text=txt, value=val, variable=self._admin_policy)\
                    .grid(row=0, column=i, sticky="w", padx=8, pady=6)
        else:
            self._admin_policy = tk.StringVar(value=self._cfg.admin_password_policy.value)  # bleibt unverändert

        # User-Schalter
        self._user_pwd = tk.BooleanVar(value=self._cfg.user_pwd_required)
        ttk.Checkbutton(self, text=T("core_signature.user.require_pwd") or "Ask password on signing",
                        variable=self._user_pwd).grid(row=3, column=0, sticky="w", padx=12, pady=(8, 0))

        # --- Management-Block
        mgf = ttk.LabelFrame(self, text=T("core_signature.manage") or "Manage signature")
        mgf.grid(row=4, column=0, sticky="ew", padx=12, pady=(8, 8))
        mgf.columnconfigure(1, weight=1)

        self._status = ttk.Label(mgf, text="")
        self._status.grid(row=0, column=0, columnspan=3, sticky="w", padx=8, pady=(6, 8))

        ttk.Button(mgf, text=T("core_signature.manage.show") or "Show…", command=self._show_sig)\
            .grid(row=1, column=0, sticky="w", padx=8, pady=4)
        ttk.Button(mgf, text=T("core_signature.manage.capture") or "Create/Replace…", command=self._capture)\
            .grid(row=1, column=1, sticky="w", padx=8, pady=4)
        ttk.Button(mgf, text=T("core_signature.manage.import") or "Import PNG…", command=self._import_sig)\
            .grid(row=1, column=2, sticky="w", padx=8, pady=4)

        ttk.Button(mgf, text=T("core_signature.manage.export") or "Export PNG…", command=self._export_sig)\
            .grid(row=2, column=0, sticky="w", padx=8, pady=(0, 6))
        ttk.Button(mgf, text=T("core_signature.manage.delete") or "Delete", command=self._delete_sig)\
            .grid(row=2, column=1, sticky="w", padx=8, pady=(0, 6))

        # --- Save
        btns = ttk.Frame(self); btns.grid(row=5, column=0, sticky="e", padx=12, pady=12)
        ttk.Button(btns, text=T("common.save") or "Save", command=self._save).pack(side="right")

        self._refresh_status()

    # ---------------- intern: Management ----------------
    def _has_sig(self) -> bool:
        uid = getattr(self._user, "id", None)
        return bool(uid) and (self._svc.load_user_signature_png(uid) is not None)

    def _refresh_status(self):
        self._status.config(text=(T("core_signature.status.ok") or "Signature stored.") if self._has_sig()
                            else (T("core_signature.status.missing") or "No signature stored."))

    def _show_sig(self):
        if not self._has_sig():
            messagebox.showinfo(T("common.info") or "Info",
                                T("core_signature.status.missing") or "No signature stored.", parent=self)
            return
        uid = getattr(self._user, "id", None)
        data = self._svc.load_user_signature_png(uid)
        im = Image.open(io.BytesIO(data)).convert("RGBA")
        w, h = im.size
        # kleiner Preview-Dialog
        top = tk.Toplevel(self); top.title(T("core_signature.manage.show") or "Show signature")
        top.transient(self); top.grab_set()
        scale = min(1.0, 400 / max(w, h))
        im2 = im.resize((max(1, int(w * scale)), max(1, int(h * scale))))
        tkimg = ImageTk.PhotoImage(im2)
        lbl = ttk.Label(top, image=tkimg); lbl.image = tkimg  # keep ref
        lbl.pack(padx=10, pady=10)
        ttk.Button(top, text=T("common.close") or "Close", command=top.destroy).pack(pady=(0, 10))

    def _capture(self):
        dlg = SignatureCaptureDialog(self, service=self._svc)
        self.wait_window(dlg)
        self._refresh_status()

    def _import_sig(self):
        p = filedialog.askopenfilename(parent=self, title=T("core_signature.manage.import") or "Import signature",
                                       filetypes=[("PNG", "*.png"), ("GIF", "*.gif")])
        if not p:
            return
        uid = getattr(self._user, "id", None)
        with open(p, "rb") as f:
            buf = f.read()
        # optional: Größe prüfen
        if len(buf) > 5 * 1024 * 1024:
            messagebox.showerror(T("common.error") or "Error", "File too large.", parent=self)
            return
        self._svc.save_user_signature_png(uid, buf)
        self._refresh_status()
        messagebox.showinfo(T("common.saved") or "Saved", T("core_signature.manage.import.ok") or "Imported.")

    def _export_sig(self):
        if not self._has_sig():
            messagebox.showinfo(T("common.info") or "Info",
                                T("core_signature.status.missing") or "No signature stored.", parent=self)
            return
        p = filedialog.asksaveasfilename(parent=self, title=T("core_signature.manage.export") or "Export signature",
                                         defaultextension=".png", filetypes=[("PNG", "*.png")])
        if not p:
            return
        uid = getattr(self._user, "id", None)
        data = self._svc.load_user_signature_png(uid)
        with open(p, "wb") as f:
            f.write(data)
        messagebox.showinfo(T("common.saved") or "Saved", T("core_signature.manage.export.ok") or "Exported.")

    def _delete_sig(self):
        if not self._has_sig():
            return
        if not messagebox.askyesno(T("common.confirm") or "Confirm",
                                   T("core_signature.manage.delete.q") or "Delete the stored signature?",
                                   parent=self):
            return
        # Passwortbestätigung (Policy-unabhängig sinnvoll)
        attempts = 0
        uid = getattr(self._user, "id", None)
        while attempts < 3:
            dlg = PasswordPromptDialog(self); self.wait_window(dlg)
            if not dlg.password:
                return
            if self._svc.verify_password(uid, dlg.password):
                break
            attempts += 1
            messagebox.showerror(T("common.error") or "Error",
                                 T("core_signature.password.wrong") or "Wrong password.", parent=self)
        if attempts >= 3:
            return

        ok = self._svc.delete_user_signature(uid)
        self._refresh_status()
        if ok:
            messagebox.showinfo(T("common.done") or "Done", T("core_signature.manage.delete.ok") or "Deleted.")

    # ---------------- intern: Save settings ----------------
    def _save(self):
        col = (self._label_color.get() or "").strip()
        if not col.startswith("#") or len(col) not in (4, 7):
            messagebox.showerror("Color", "Please use a hex color like #000 or #000000.", parent=self)
            return

        cfg = self._svc.load_config()
        cfg.name_position = LabelPosition(self._name_pos.get())
        cfg.date_position = LabelPosition(self._date_pos.get())
        cfg.date_format = self._date_fmt.get().strip() or "%Y-%m-%d %H:%M"
        cfg.label_color = col
        cfg.name_font_size = max(6, int(self._name_fs.get()))
        cfg.date_font_size = max(6, int(self._date_fs.get()))
        cfg.embed_name = bool(self._embed_name.get())
        cfg.embed_date = bool(self._embed_date.get())
        cfg.user_pwd_required = bool(self._user_pwd.get())

        # Admin-Policy nur schreiben, wenn Admin-Bereich sichtbar war
        try:
            role = getattr(self._user, "role", None)
            if (role == UserRole.ADMIN) or (getattr(role, "name", "").upper() == "ADMIN"):
                cfg.admin_password_policy = AdminPasswordPolicy(self._admin_policy.get())
        except Exception:
            pass

        self._svc.save_config(cfg)
        messagebox.showinfo(T("common.saved") or "Saved", "Einstellungen gespeichert.")
