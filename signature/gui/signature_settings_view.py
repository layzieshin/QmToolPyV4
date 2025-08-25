from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from core.common.app_context import AppContext, T
from core.settings.logic.settings_manager import SettingsManager
from ..models.signature_config import SignatureConfig
from ..models.signature_enums import LabelPosition, OutputNamingMode, AdminPasswordPolicy

class SignatureSettingsView(ttk.Frame):
    """
    Settings-Tab für das Signature-Modul.
    Neu: Eingabe der Label-Farbe (Hex, z.B. #000000).
    """

    def __init__(self, parent: tk.Misc, *, settings_manager: SettingsManager) -> None:
        super().__init__(parent)
        self._sm = settings_manager
        self._cfg = self._load()

        self.columnconfigure(0, weight=1)

        title = ttk.Label(self, text=T("core_signature.settings.title") or "Signature Settings",
                          font=("Segoe UI", 14, "bold"))
        title.grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))

        frm = ttk.Frame(self)
        frm.grid(row=1, column=0, sticky="nsew", padx=12, pady=8)

        # Name/Datum / Position
        ttk.Label(frm, text=T("core_signature.name_pos") or "Name position").grid(row=0, column=0, sticky="w")
        self._name_pos = tk.StringVar(value=self._cfg.name_position.value)
        ttk.Combobox(frm, textvariable=self._name_pos, values=[v.value for v in LabelPosition], state="readonly", width=12)\
            .grid(row=0, column=1, sticky="w", padx=(6, 20))

        ttk.Label(frm, text=T("core_signature.date_pos") or "Date position").grid(row=0, column=2, sticky="w")
        self._date_pos = tk.StringVar(value=self._cfg.date_position.value)
        ttk.Combobox(frm, textvariable=self._date_pos, values=[v.value for v in LabelPosition], state="readonly", width=12)\
            .grid(row=0, column=3, sticky="w", padx=(6, 20))

        # Datumformat
        ttk.Label(frm, text=T("core_signature.date_format") or "Date format (strftime)").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self._date_fmt = tk.StringVar(value=self._cfg.date_format)
        ttk.Entry(frm, textvariable=self._date_fmt, width=16).grid(row=1, column=1, sticky="w", padx=(6, 20), pady=(8, 0))

        # Farbe (Hex)
        ttk.Label(frm, text="Label-Farbe (Hex)").grid(row=1, column=2, sticky="w", pady=(8, 0))
        self._label_color = tk.StringVar(value=self._cfg.label_color or "#000000")
        ttk.Entry(frm, textvariable=self._label_color, width=12).grid(row=1, column=3, sticky="w", padx=(6, 20), pady=(8, 0))

        # Embedding flags
        self._embed_name = tk.BooleanVar(value=self._cfg.embed_name)
        self._embed_date = tk.BooleanVar(value=self._cfg.embed_date)
        ttk.Checkbutton(frm, text=T("core_signature.embed_name") or "Embed user name in signature image",
                        variable=self._embed_name).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8,0))
        ttk.Checkbutton(frm, text=T("core_signature.embed_date") or "Embed date in signature image",
                        variable=self._embed_date).grid(row=2, column=2, columnspan=2, sticky="w", pady=(8,0))

        # Passwort-Policy (Admin)
        admf = ttk.LabelFrame(self, text=T("core_signature.admin.policy_title") or "Password policy (Admin)")
        admf.grid(row=2, column=0, sticky="ew", padx=12, pady=(8, 0))
        self._admin_policy = tk.StringVar(value=self._cfg.admin_password_policy.value)
        for i, (txt, val) in enumerate((
            (T("core_signature.admin.always") or "always required", "always"),
            (T("core_signature.admin.never") or "never required", "never"),
            (T("core_signature.admin.user") or "user-specific", "user_specific"),
        )):
            ttk.Radiobutton(admf, text=txt, value=val, variable=self._admin_policy).grid(row=0, column=i, sticky="w", padx=8, pady=6)

        # Nutzer-Schalter
        self._user_pwd = tk.BooleanVar(value=self._cfg.user_pwd_required)
        ttk.Checkbutton(self, text=T("core_signature.user.require_pwd") or "Ask password on signing",
                        variable=self._user_pwd).grid(row=3, column=0, sticky="w", padx=12, pady=(8, 0))

        # Save
        btns = ttk.Frame(self); btns.grid(row=4, column=0, sticky="e", padx=12, pady=12)
        ttk.Button(btns, text=T("common.save") or "Save", command=self._save).pack(side="right")

    def _load(self) -> SignatureConfig:
        from ..logic.signature_service import SignatureService
        return SignatureService(settings_manager=self._sm).load_config()

    def _save(self):
        # sehr simple Hex-Validierung
        col = (self._label_color.get() or "").strip()
        if not col.startswith("#") or len(col) not in (4, 7):
            messagebox.showerror("Farbe", "Bitte eine gültige Hex-Farbe angeben, z. B. #000 oder #000000.", parent=self)
            return

        cfg = self._load()
        cfg.name_position = LabelPosition(self._name_pos.get())
        cfg.date_position = LabelPosition(self._date_pos.get())
        cfg.date_format = self._date_fmt.get().strip() or "%Y-%m-%d %H:%M"
        cfg.label_color = col
        cfg.embed_name = bool(self._embed_name.get())
        cfg.embed_date = bool(self._embed_date.get())
        cfg.user_pwd_required = bool(self._user_pwd.get())
        from ..models.signature_enums import AdminPasswordPolicy
        cfg.admin_password_policy = AdminPasswordPolicy(self._admin_policy.get())

        from ..logic.signature_service import SignatureService
        SignatureService(settings_manager=self._sm).save_config(cfg)
        messagebox.showinfo(T("common.saved") or "Saved", "Einstellungen gespeichert.")
