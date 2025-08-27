# signature/gui/signature_settings_view.py
from __future__ import annotations
import io
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from PIL import Image, ImageTk, ImageEnhance

from core.common.app_context import AppContext, T
from core.settings.logic.settings_manager import SettingsManager
from core.models.user import UserRole

from ..models.signature_enums import LabelPosition, AdminPasswordPolicy
from ..models.label_offsets import LabelOffsets
from ..logic.signature_service import SignatureService
from .signature_capture_dialog import SignatureCaptureDialog
from .password_prompt_dialog import PasswordPromptDialog


def settings_visibility_predicate() -> bool:
    return getattr(AppContext, "current_user", None) is not None


class SignatureSettingsView(ttk.Frame):
    """Settings tab with management, user/admin offsets and live preview."""
    PREVIEW_W = 320
    PREVIEW_H = 180
    _SIG_SAMPLE_W_PT = 180.0

    def __init__(self, parent: tk.Misc, *, settings_manager: SettingsManager | None = None,
                 sm: SettingsManager | None = None, **kwargs) -> None:
        super().__init__(parent)
        self._sm: SettingsManager | None = settings_manager or sm

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
        cfg = self._svc.load_config()
        self.columnconfigure(0, weight=1)

        # Toolbar
        topbar = ttk.Frame(self)
        topbar.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 0))
        topbar.columnconfigure(0, weight=1)
        ttk.Label(topbar, text=T("core_signature.settings.title") or "Signature Settings",
                  font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Button(topbar, text=T("common.save") or "Save", command=self._save).grid(row=0, column=1, sticky="e")
        self.bind_all("<Control-s>", lambda e: self._save())

        # Main
        frm = ttk.Frame(self); frm.grid(row=1, column=0, sticky="nsew", padx=12, pady=8)

        ttk.Label(frm, text=T("core_signature.name_pos") or "Name position").grid(row=0, column=0, sticky="w")
        self._name_pos = tk.StringVar(value=cfg.name_position.value)
        self._name_pos_cb = ttk.Combobox(frm, textvariable=self._name_pos,
                                         values=[v.value for v in LabelPosition], state="readonly", width=12)
        self._name_pos_cb.grid(row=0, column=1, sticky="w", padx=(6, 20))

        ttk.Label(frm, text=T("core_signature.date_pos") or "Date position").grid(row=0, column=2, sticky="w")
        self._date_pos = tk.StringVar(value=cfg.date_position.value)
        self._date_pos_cb = ttk.Combobox(frm, textvariable=self._date_pos,
                                         values=[v.value for v in LabelPosition], state="readonly", width=12)
        self._date_pos_cb.grid(row=0, column=3, sticky="w", padx=(6, 20))

        ttk.Label(frm, text=T("core_signature.date_format") or "Date format (strftime)")\
            .grid(row=1, column=0, sticky="w", pady=(8, 0))
        self._date_fmt = tk.StringVar(value=cfg.date_format)
        e_fmt = ttk.Entry(frm, textvariable=self._date_fmt, width=16)
        e_fmt.grid(row=1, column=1, sticky="w", padx=(6, 20), pady=(8, 0))

        ttk.Label(frm, text="Label color (hex)").grid(row=1, column=2, sticky="w", pady=(8, 0))
        self._label_color = tk.StringVar(value=cfg.label_color or "#000000")
        e_col = ttk.Entry(frm, textvariable=self._label_color, width=12)
        e_col.grid(row=1, column=3, sticky="w", padx=(6, 20), pady=(8, 0))

        ttk.Label(frm, text="Name font size (pt)").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self._name_fs = tk.IntVar(value=max(6, int(cfg.name_font_size)))
        self._name_fs_sb = ttk.Spinbox(frm, from_=6, to=48, textvariable=self._name_fs, width=6)
        self._name_fs_sb.grid(row=2, column=1, sticky="w", padx=(6, 20), pady=(8, 0))

        ttk.Label(frm, text="Date font size (pt)").grid(row=2, column=2, sticky="w", pady=(8, 0))
        self._date_fs = tk.IntVar(value=max(6, int(cfg.date_font_size)))
        self._date_fs_sb = ttk.Spinbox(frm, from_=6, to=48, textvariable=self._date_fs, width=6)
        self._date_fs_sb.grid(row=2, column=3, sticky="w", padx=(6, 20), pady=(8, 0))

        self._embed_name = tk.BooleanVar(value=cfg.embed_name)
        self._embed_date = tk.BooleanVar(value=cfg.embed_date)
        cb_sn = ttk.Checkbutton(frm, text=T("core_signature.embed_name") or "Show name", variable=self._embed_name)
        cb_sd = ttk.Checkbutton(frm, text=T("core_signature.embed_date") or "Show date", variable=self._embed_date)
        cb_sn.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        cb_sd.grid(row=3, column=2, columnspan=2, sticky="w", pady=(8, 0))

        # User Offsets
        off = cfg.label_offsets
        off_frame = ttk.LabelFrame(self, text=T("core_signature.offsets.user") or "Offsets (user)")
        off_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))

        ttk.Label(off_frame, text="Name above (pt)").grid(row=0, column=0, sticky="w")
        self._u_name_above = tk.DoubleVar(value=off.name_above)
        self._u_name_above_sb = ttk.Spinbox(off_frame, from_=0, to=100, increment=0.5, textvariable=self._u_name_above, width=7)
        self._u_name_above_sb.grid(row=0, column=1, sticky="w", padx=(6, 12))

        ttk.Label(off_frame, text="Name below (pt)").grid(row=0, column=2, sticky="w")
        self._u_name_below = tk.DoubleVar(value=off.name_below)
        self._u_name_below_sb = ttk.Spinbox(off_frame, from_=0, to=100, increment=0.5, textvariable=self._u_name_below, width=7)
        self._u_name_below_sb.grid(row=0, column=3, sticky="w", padx=(6, 12))

        ttk.Label(off_frame, text="Date above (pt)").grid(row=0, column=4, sticky="w")
        self._u_date_above = tk.DoubleVar(value=off.date_above)
        self._u_date_above_sb = ttk.Spinbox(off_frame, from_=0, to=100, increment=0.5, textvariable=self._u_date_above, width=7)
        self._u_date_above_sb.grid(row=0, column=5, sticky="w", padx=(6, 12))

        ttk.Label(off_frame, text="Date below (pt)").grid(row=0, column=6, sticky="w")
        self._u_date_below = tk.DoubleVar(value=off.date_below)
        self._u_date_below_sb = ttk.Spinbox(off_frame, from_=0, to=100, increment=0.5, textvariable=self._u_date_below, width=7)
        self._u_date_below_sb.grid(row=0, column=7, sticky="w", padx=(6, 12))

        ttk.Label(off_frame, text="Left indent (pt)").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self._u_x_offset = tk.DoubleVar(value=off.x_offset)
        self._u_x_offset_sb = ttk.Spinbox(off_frame, from_=-50, to=50, increment=0.5, textvariable=self._u_x_offset, width=7)
        self._u_x_offset_sb.grid(row=1, column=1, sticky="w", padx=(6, 12), pady=(6, 0))

        # Admin defaults
        show_admin = False
        try:
            role = getattr(self._user, "role", None)
            show_admin = (role == UserRole.ADMIN) or (getattr(role, "name", "").upper() == "ADMIN")
        except Exception:
            pass

        if show_admin:
            g_off = self._svc.load_global_offset_defaults()
            gadm = ttk.LabelFrame(self, text=T("core_signature.offsets.admin") or "Default offsets (admin)")
            gadm.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 8))

            ttk.Label(gadm, text="Name above (pt)").grid(row=0, column=0, sticky="w")
            self._g_name_above = tk.DoubleVar(value=g_off.name_above)
            ttk.Spinbox(gadm, from_=0, to=100, increment=0.5, textvariable=self._g_name_above, width=7)\
                .grid(row=0, column=1, sticky="w", padx=(6, 12))

            ttk.Label(gadm, text="Name below (pt)").grid(row=0, column=2, sticky="w")
            self._g_name_below = tk.DoubleVar(value=g_off.name_below)
            ttk.Spinbox(gadm, from_=0, to=100, increment=0.5, textvariable=self._g_name_below, width=7)\
                .grid(row=0, column=3, sticky="w", padx=(6, 12))

            ttk.Label(gadm, text="Date above (pt)").grid(row=0, column=4, sticky="w")
            self._g_date_above = tk.DoubleVar(value=g_off.date_above)
            ttk.Spinbox(gadm, from_=0, to=100, increment=0.5, textvariable=self._g_date_above, width=7)\
                .grid(row=0, column=5, sticky="w", padx=(6, 12))

            ttk.Label(gadm, text="Date below (pt)").grid(row=0, column=6, sticky="w")
            self._g_date_below = tk.DoubleVar(value=g_off.date_below)
            ttk.Spinbox(gadm, from_=0, to=100, increment=0.5, textvariable=self._g_date_below, width=7)\
                .grid(row=0, column=7, sticky="w", padx=(6, 12))

            ttk.Label(gadm, text="Left indent (pt)").grid(row=1, column=0, sticky="w", pady=(6, 0))
            self._g_x_offset = tk.DoubleVar(value=g_off.x_offset)
            ttk.Spinbox(gadm, from_=-50, to=50, increment=0.5, textvariable=self._g_x_offset, width=7)\
                .grid(row=1, column=1, sticky="w", padx=(6, 12), pady=(6, 0))

            ttk.Button(gadm, text=T("core_signature.offsets.reset_user") or "Apply defaults to user",
                       command=self._apply_admin_defaults_to_user).grid(row=1, column=7, sticky="e", padx=6)

            self._admin_policy = tk.StringVar(value=cfg.admin_password_policy.value)
            apf = ttk.LabelFrame(self, text=T("core_signature.admin.policy_title") or "Password policy (Admin)")
            apf.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 8))
            for i, (txt, val) in enumerate(((T("core_signature.admin.always") or "always", "always"),
                                            (T("core_signature.admin.never") or "never", "never"),
                                            (T("core_signature.admin.user") or "user-specific", "user_specific"))):
                ttk.Radiobutton(apf, text=txt, value=val, variable=self._admin_policy)\
                    .grid(row=0, column=i, sticky="w", padx=8, pady=6)

        self._user_pwd = tk.BooleanVar(value=cfg.user_pwd_required)
        ttk.Checkbutton(self, text=T("core_signature.user.require_pwd") or "Ask password on signing",
                        variable=self._user_pwd).grid(row=5, column=0, sticky="w", padx=12, pady=(0, 8))

        # Manage signature
        mgf = ttk.LabelFrame(self, text=T("core_signature.manage") or "Manage signature")
        mgf.grid(row=6, column=0, sticky="ew", padx=12, pady=(0, 8)); mgf.columnconfigure(1, weight=1)

        self._status = ttk.Label(mgf, text="")
        self._status.grid(row=0, column=0, columnspan=3, sticky="w", padx=8, pady=(6, 8))

        ttk.Button(mgf, text=T("core_signature.manage.capture") or "Create/Replace…", command=self._capture)\
            .grid(row=1, column=0, sticky="w", padx=8, pady=4)
        ttk.Button(mgf, text=T("core_signature.manage.import") or "Import PNG…", command=self._import_sig)\
            .grid(row=1, column=1, sticky="w", padx=8, pady=4)
        ttk.Button(mgf, text=T("core_signature.manage.export") or "Export PNG…", command=self._export_sig)\
            .grid(row=1, column=2, sticky="w", padx=8, pady=4)
        ttk.Button(mgf, text=T("core_signature.manage.delete") or "Delete", command=self._delete_sig)\
            .grid(row=1, column=3, sticky="w", padx=8, pady=4)

        # Preview
        prevf = ttk.LabelFrame(self, text=T("core_signature.preview") or "Preview")
        prevf.grid(row=7, column=0, sticky="nsew", padx=12, pady=(0, 8))
        prevf.columnconfigure(0, weight=1); prevf.rowconfigure(0, weight=1)

        wrap = ttk.Frame(prevf); wrap.grid(row=0, column=0, sticky="nsew")
        wrap.columnconfigure(0, weight=1); wrap.rowconfigure(0, weight=1)

        self._preview = tk.Canvas(wrap, width=self.PREVIEW_W, height=self.PREVIEW_H,
                                  bg="#ffffff", highlightthickness=1, highlightbackground="#888",
                                  xscrollincrement=1, yscrollincrement=1)
        self._preview.grid(row=0, column=0, sticky="nsew")
        xsb = ttk.Scrollbar(wrap, orient="horizontal", command=self._preview.xview)
        ysb = ttk.Scrollbar(wrap, orient="vertical", command=self._preview.yview)
        self._preview.configure(xscrollcommand=xsb.set, yscrollcommand=ysb.set)
        xsb.grid(row=1, column=0, sticky="ew")
        ysb.grid(row=0, column=1, sticky="ns")

        btns = ttk.Frame(self); btns.grid(row=8, column=0, sticky="e", padx=12, pady=12)
        ttk.Button(btns, text=T("common.save") or "Save", command=self._save).pack(side="right")

        # Events
        for w in (self._name_pos_cb, self._date_pos_cb, e_fmt, e_col, self._name_fs_sb, self._date_fs_sb):
            w.bind("<<ComboboxSelected>>", lambda e: (self._update_controls_state(), self._draw_preview()))
            w.bind("<KeyRelease>", lambda e: self._draw_preview())
            w.bind("<FocusOut>", lambda e: self._draw_preview())
        for v in (self._u_name_above, self._u_name_below, self._u_date_above, self._u_date_below, self._u_x_offset):
            v.trace_add("write", lambda *_: self._draw_preview())
        for chk in (cb_sn, cb_sd):
            chk.configure(command=self._draw_preview)

        self._prev_sig_tk = None
        self._refresh_status()
        self._update_controls_state()
        self._draw_preview()

    # ---- helpers / state ----
    def _apply_admin_defaults_to_user(self):
        g = self._svc.load_global_offset_defaults()
        self._u_name_above.set(g.name_above)
        self._u_name_below.set(g.name_below)
        self._u_date_above.set(g.date_above)
        self._u_date_below.set(g.date_below)
        self._u_x_offset.set(g.x_offset)
        self._draw_preview()

    def _update_controls_state(self):
        """Disable offset/font inputs when position is OFF."""
        npos = LabelPosition(self._name_pos.get())
        dpos = LabelPosition(self._date_pos.get())

        for w in (self._name_fs_sb, self._u_name_above_sb, self._u_name_below_sb):
            w.configure(state=("disabled" if npos == LabelPosition.OFF else "normal"))
        for w in (self._date_fs_sb, self._u_date_above_sb, self._u_date_below_sb):
            w.configure(state=("disabled" if dpos == LabelPosition.OFF else "normal"))

    # ---- status / mgmt ----
    def _has_sig(self) -> bool:
        uid = getattr(self._user, "id", None)
        return bool(uid) and (self._svc.load_user_signature_png(uid) is not None)

    def _refresh_status(self):
        self._status.config(text=(T("core_signature.status.ok") or "Signature stored.") if self._has_sig()
                            else (T("core_signature.status.missing") or "No signature stored."))

    def _capture(self):
        dlg = SignatureCaptureDialog(self, service=self._svc)
        self.wait_window(dlg)
        self._refresh_status(); self._draw_preview()

    def _import_sig(self):
        p = filedialog.askopenfilename(parent=self, title=T("core_signature.manage.import") or "Import signature",
                                       filetypes=[("PNG", "*.png"), ("GIF", "*.gif")])
        if not p: return
        uid = getattr(self._user, "id", None)
        with open(p, "rb") as f: buf = f.read()
        if len(buf) > 5 * 1024 * 1024:
            messagebox.showerror(T("common.error") or "Error", "File too large.", parent=self); return
        self._svc.save_user_signature_png(uid, buf)
        self._refresh_status(); self._draw_preview()

    def _export_sig(self):
        if not self._has_sig():
            messagebox.showinfo(T("common.info") or "Info",
                                T("core_signature.status.missing") or "No signature stored.", parent=self); return
        p = filedialog.asksaveasfilename(parent=self, title=T("core_signature.manage.export") or "Export signature",
                                         defaultextension=".png", filetypes=[("PNG", "*.png")])
        if not p: return
        uid = getattr(self._user, "id", None)
        data = self._svc.load_user_signature_png(uid)
        with open(p, "wb") as f: f.write(data)
        messagebox.showinfo(T("common.saved") or "Saved", T("core_signature.manage.export.ok") or "Exported.")

    def _delete_sig(self):
        if not self._has_sig(): return
        if not messagebox.askyesno(T("common.confirm") or "Confirm",
                                   T("core_signature.manage.delete.q") or "Delete the stored signature?",
                                   parent=self):
            return
        attempts = 0; uid = getattr(self._user, "id", None)
        while attempts < 3:
            from .password_prompt_dialog import PasswordPromptDialog
            dlg = PasswordPromptDialog(self); self.wait_window(dlg)
            if not dlg.password: return
            if self._svc.verify_password(uid, dlg.password): break
            attempts += 1
            messagebox.showerror(T("common.error") or "Error",
                                 T("core_signature.password.wrong") or "Wrong password.", parent=self)
        if attempts >= 3: return

        if self._svc.delete_user_signature(uid):
            self._refresh_status(); self._draw_preview()
            messagebox.showinfo(T("common.done") or "Done", T("core_signature.manage.delete.ok") or "Deleted.")

    # ---- save ----
    def _save(self):
        try:
            col = (self._label_color.get() or "").strip()
            if not col.startswith("#") or len(col) not in (4, 7):
                messagebox.showerror("Color", "Please use a hex color like #000 or #000000.", parent=self); return

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

            cfg.label_offsets = LabelOffsets(
                name_above=float(self._u_name_above.get()),
                name_below=float(self._u_name_below.get()),
                date_above=float(self._u_date_above.get()),
                date_below=float(self._u_date_below.get()),
                x_offset=float(self._u_x_offset.get()),
            )

            is_admin = False
            try:
                role = getattr(self._user, "role", None)
                is_admin = (role == UserRole.ADMIN) or (getattr(role, "name", "").upper() == "ADMIN")
            except Exception:
                pass

            if is_admin and hasattr(self, "_g_name_above"):
                self._svc.save_global_offset_defaults(LabelOffsets(
                    name_above=float(self._g_name_above.get()),
                    name_below=float(self._g_name_below.get()),
                    date_above=float(self._g_date_above.get()),
                    date_below=float(self._g_date_below.get()),
                    x_offset=float(self._g_x_offset.get()),
                ))
                try:
                    cfg.admin_password_policy = AdminPasswordPolicy(self._admin_policy.get())
                except Exception:
                    pass

            self._svc.save_config(cfg)
            self._update_controls_state()
            self._draw_preview()
            messagebox.showinfo(T("common.saved") or "Saved", T("core_signature.saved") or "Settings saved.", parent=self)
        except Exception as ex:
            messagebox.showerror(T("common.error") or "Error", str(ex), parent=self)

    # ---- preview ----
    def _draw_preview(self):
        cv = self._preview
        cv.delete("all")

        sig_w_pt = float(self._SIG_SAMPLE_W_PT)
        sig_data = self._svc.load_user_signature_png(getattr(self._user, "id", None))
        sig_aspect = 0.30; pil_sig = None
        if sig_data:
            try:
                pil_sig = Image.open(io.BytesIO(sig_data)).convert("RGBA")
                if pil_sig.width > 0:
                    sig_aspect = pil_sig.height / pil_sig.width
            except Exception:
                pil_sig = None
        sig_h_pt = sig_w_pt * sig_aspect

        margin = 12
        total_w_pt = sig_w_pt + 120.0
        total_h_pt = sig_h_pt + 60.0 + 60.0
        sx = (self.PREVIEW_W - 2 * margin) / total_w_pt
        sy = (self.PREVIEW_H - 2 * margin) / total_h_pt
        scale = min(max(0.3, sx), max(0.3, sy))

        x0 = margin
        y0 = margin + (self.PREVIEW_H - 2 * margin - sig_h_pt * scale) / 2
        x1 = x0 + sig_w_pt * scale
        y1 = y0 + sig_h_pt * scale

        cv.create_rectangle(0, 0, self.PREVIEW_W, self.PREVIEW_H, fill="#fff", outline="")
        cv.create_rectangle(x0, y0, x1, y1, outline="#0A84FF", fill="#EAF4FF")

        if pil_sig is not None:
            wpx, hpx = int(sig_w_pt * scale), int(sig_h_pt * scale)
            img = pil_sig.resize((max(1, wpx), max(1, hpx)), Image.LANCZOS)
            r, g, b, a = img.split()
            a = ImageEnhance.Brightness(a).enhance(0.65)
            img = Image.merge("RGBA", (r, g, b, a))
            self._prev_sig_tk = ImageTk.PhotoImage(img)
            cv.create_image(x0, y0, image=self._prev_sig_tk, anchor="nw")

        col = (self._label_color.get() or "#000000").strip()
        if not (col.startswith("#") and len(col) in (4, 7)):
            col = "#000000"

        full_name = (getattr(self._user, "full_name", None)
                     or getattr(self._user, "name", None)
                     or getattr(self._user, "username", None) or "")
        import datetime as _dt
        ts = _dt.datetime.now().strftime(self._date_fmt.get() or "%Y-%m-%d %H:%M")

        off = LabelOffsets(
            name_above=float(self._u_name_above.get()),
            name_below=float(self._u_name_below.get()),
            date_above=float(self._u_date_above.get()),
            date_below=float(self._u_date_below.get()),
            x_offset=float(self._u_x_offset.get()),
        )

        left_px = x0 + off.x_offset * scale
        name_px = max(1, int(self._name_fs.get() * scale))
        date_px = max(1, int(self._date_fs.get() * scale))

        npos = LabelPosition(self._name_pos.get())
        dpos = LabelPosition(self._date_pos.get())

        if self._embed_name.get() and full_name and npos != LabelPosition.OFF:
            if npos == LabelPosition.ABOVE:
                y = y0 - off.name_above * scale
            else:
                y = y1 + off.name_below * scale
            cv.create_text(left_px, y, text=full_name, anchor="sw",
                           font=("Segoe UI", -name_px, "bold"), fill=col)

        if self._embed_date.get() and dpos != LabelPosition.OFF:
            if dpos == LabelPosition.ABOVE:
                y = y0 - off.date_above * scale
            else:
                y = y1 + off.date_below * scale
            cv.create_text(left_px, y, text=ts, anchor="sw",
                           font=("Segoe UI", -date_px, "bold"), fill=col)

        bbox = cv.bbox("all")
        if bbox:
            cv.configure(scrollregion=bbox)
