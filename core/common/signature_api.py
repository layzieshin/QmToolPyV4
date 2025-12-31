# core/common/signature_api.py
from __future__ import annotations

from typing import Optional, Tuple, Union, Any

from core.settings.logic.settings_manager import SettingsManager

# Fallback-Logger (falls AppContext.logger fehlt)
try:
    from core.qm_logging.logic.logger import logger as default_logger  # type: ignore
except Exception:
    default_logger = None  # type: ignore


class SignatureAPI:
    """
    Thin facade around SignatureService, designed for global use via AppContext.signature().

    WICHTIG:
    - Kein Top-Level-Import von AppContext oder Signature-Modulen (lazy in Methoden).
    - Policy, i18n & Logging werden zentral in der Service-Logik respektiert.
    """

    def __init__(self) -> None:
        self._svc = None  # lazy

    # ---------------- lazy context helpers ----------------
    @staticmethod
    def _ctx():
        """Lazy Import von AppContext; None wenn noch nicht initialisiert."""
        try:
            from core.common.app_context import AppContext  # noqa
            return AppContext
        except Exception:
            return None

    @staticmethod
    def _t(key: str) -> Optional[str]:
        """Lazy Zugriff auf T(...) im AppContext; None wenn nicht verfügbar."""
        ctx = SignatureAPI._ctx()
        if ctx is None:
            return None
        fn = getattr(ctx, "T", None) or getattr(ctx, "translate", None)
        if callable(fn):
            try:
                return fn(key)  # type: ignore[misc]
            except Exception:
                return None
        return None

    def _get_service(self):
        """Lazy Initialisierung des SignatureService mit Settings/Logger aus dem AppContext."""
        if self._svc is not None:
            return self._svc

        # Lazy import hier, um Zirkularimporte sicher auszuschließen
        from signature.logic.signature_service import SignatureService  # lazy

        ctx = self._ctx()
        sm = getattr(ctx, "settings_manager", None) if ctx else None
        if sm is None:
            sm = SettingsManager()
            try:
                if ctx:
                    ctx.settings_manager = sm  # type: ignore[attr-defined]
            except Exception:
                pass

        log = getattr(ctx, "logger", None) if ctx else None
        log = log or default_logger
        self._svc = SignatureService(settings_manager=sm, logger=log)  # type: ignore[arg-type]
        return self._svc

    def _log(self, event: str, **data) -> None:
        """Logger-Helper: reichert Logdaten mit User-Kontext an (falls vorhanden)."""
        ctx = self._ctx()
        user = getattr(ctx, "current_user", None) if ctx else None
        uinfo = {
            "user_id": getattr(user, "id", None),
            "username": getattr(user, "username", None),
        }
        log = getattr(ctx, "logger", None) if ctx else None
        log = log or default_logger
        if log and hasattr(log, "log"):
            try:
                log.log(feature="Signature", event=event, **uinfo, **data)
            except Exception:
                pass

    # ---------------- capability checks ----------------
    def is_available(self) -> bool:
        """True, wenn ein User eingeloggt ist und Settings verfügbar sind."""
        ctx = self._ctx()
        return bool(ctx and getattr(ctx, "current_user", None) and getattr(ctx, "settings_manager", None))

    def has_signature(self) -> bool:
        """True, wenn der aktuelle Benutzer eine gespeicherte Signatur hat."""
        ctx = self._ctx()
        user = getattr(ctx, "current_user", None) if ctx else None
        uid = getattr(user, "id", None)
        if uid is None:
            return False
        svc = self._get_service()
        return svc.load_user_signature_png(uid) is not None  # type: ignore[arg-type]

    def ensure_signature_or_raise(self) -> None:
        """RuntimeError, wenn keine gespeicherte Signatur vorhanden ist (mit i18n & Logging)."""
        if not self.has_signature():
            self._log("EnsureSignatureMissing")
            msg = self._t("core_signature.api.no_signature") or "No stored signature for current user."
            raise RuntimeError(msg)

    # ---------------- high-level UI flow (for GUI modules) ----------------
    def place_and_sign(
        self,
        parent: Any,
        pdf_path: str,
        *,
        reason: Optional[str] = "manual",
        force_password: Optional[bool] = None,
        initial_width_pt: float | None = None,
    ) -> Optional[str]:
        """
        Öffnet den Platzierungs-Dialog (Zoom, Pan, Drag&Drop) und signiert bei Bestätigung.
        Gibt den Output-Pfad zurück oder None bei Abbruch.
        """
        if not pdf_path:
            return None

        ctx = self._ctx()
        user = getattr(ctx, "current_user", None)
        if not user:
            raise RuntimeError("No current user; signing requires authentication.")

        svc = self._get_service()

        # Sicherstellen: Signatur vorhanden – sonst On-the-fly erfassen
        uid = getattr(user, "id", None)
        sig = svc.load_user_signature_png(uid) if uid else None
        if not sig:
            from tkinter import messagebox
            from core.common.app_context import T as _T  # lazy
            if not messagebox.askyesno(_T("common.question") or "Question",
                                       _T("core_signature.sign.no_sig_q") or "No signature stored. Create one now?",
                                       parent=parent):
                return None
            from signature.gui.signature_capture_dialog import SignatureCaptureDialog  # lazy
            dlg = SignatureCaptureDialog(parent, service=svc)
            parent.wait_window(dlg)
            sig = svc.load_user_signature_png(uid)
            if not sig:
                return None

        # Defaults & Dialog öffnen
        cfg = svc.load_config()
        from signature.models.signature_placement import SignaturePlacement  # lazy
        from signature.gui.placement_dialog import PlacementDialog  # lazy

        init_w = float(initial_width_pt) if initial_width_pt else max(120.0, 180.0)
        label_name = (
            getattr(user, "full_name", None)
            or getattr(user, "name", None)
            or getattr(user, "username", None)
            or ""
        )

        dlg = PlacementDialog(
            parent,
            pdf_path=pdf_path,
            default_placement=SignaturePlacement(page_index=0, x=72.0, y=72.0, target_width=init_w),
            default_name_pos=cfg.name_position,
            default_date_pos=cfg.date_position,
            default_offsets=cfg.label_offsets,
            signature_png=sig,
            show_name=bool(cfg.embed_name),
            show_date=bool(cfg.embed_date),
            label_name_text=label_name,
            date_format=cfg.date_format,
            label_color_hex=cfg.label_color,
            name_font_size=cfg.name_font_size,
            date_font_size=cfg.date_font_size,
        )
        parent.wait_window(dlg)
        if not dlg.result:
            return None

        # 3- oder 4-Tuple kompatibel handhaben
        placement, pos_pair, offsets = dlg.result[0], dlg.result[1], dlg.result[2]
        font_sizes: Tuple[int, int] = (cfg.name_font_size, cfg.date_font_size)
        if len(dlg.result) >= 4:
            font_sizes = dlg.result[3]

        # Passwortpolicy
        must_pwd = svc.is_password_required()
        if force_password is not None:
            must_pwd = bool(force_password)

        if must_pwd:
            from tkinter import messagebox
            from signature.gui.password_prompt_dialog import PasswordPromptDialog  # lazy
            attempts = 0
            while attempts < 3:
                pd = PasswordPromptDialog(parent)
                parent.wait_window(pd)
                if not pd.password:
                    return None
                if svc.verify_password(uid, pd.password):
                    break
                attempts += 1
                messagebox.showerror("Error", "Wrong password.", parent=parent)
            if attempts >= 3:
                return None

        # Signieren
        out_path = svc.sign_pdf(
            input_path=pdf_path,
            placement=placement,
            enforce_label_positions=pos_pair,
            override_label_offsets=offsets,
            override_font_sizes=font_sizes,
            reason=reason,
        )
        return out_path

    # ---------------- headless API ----------------
    def sign_pdf(
        self,
        *,
        input_path: str,
        placement,  # SignaturePlacement (lazy typisiert unten)
        reason: Optional[str] = "auto",
        enforce_label_positions: Optional[Tuple["LabelPosition", "LabelPosition"]] = None,
        override_label_offsets: Optional["LabelOffsets"] = None,
        override_font_sizes: Optional[Tuple[int, int]] = None,
        password: Optional[str] = None,
        ignore_password_policy: bool = False,
        override_output: Optional[str] = None,
    ) -> str:
        """
        PDF für den aktuellen AppContext-User signieren (headless-fähig).

        Security:
          - Falls Policy ein Passwort verlangt, muss `password` gesetzt sein,
            außer `ignore_password_policy=True` (nur für vertrauenswürdige Automationen).
        """
        # Lazy type imports (nur für Annotation-Auflösung/IDE)
        from signature.models.signature_enums import LabelPosition  # noqa: F401
        from signature.models.label_offsets import LabelOffsets  # noqa: F401

        svc = self._get_service()
        ctx = self._ctx()
        user = getattr(ctx, "current_user", None) if ctx else None
        uid = getattr(user, "id", None)
        if uid is None:
            self._log("APISignFailed", reason="NoUserInContext")
            msg = self._t("core_signature.api.no_user") or "No logged-in user in AppContext."
            raise RuntimeError(msg)

        # Policy durchsetzen
        if svc.is_password_required():
            if ignore_password_policy:
                self._log("PasswordPolicyBypassed", reason=reason)
            else:
                if not password:
                    self._log("PasswordRequiredMissing", reason=reason)
                    msg = self._t("core_signature.api.password_required") \
                          or "Password required by policy. Provide `password` or adjust settings."
                    raise PermissionError(msg)
                if not svc.verify_password(uid, password):  # type: ignore[arg-type]
                    self._log("PasswordVerifyFailed", reason=reason)
                    msg = self._t("core_signature.api.password_invalid") or "Invalid password."
                    raise PermissionError(msg)

        # Start-Log
        self._log(
            "APISignStart",
            input_path=input_path,
            page=getattr(placement, "page_index", None),
            x=getattr(placement, "x", None),
            y=getattr(placement, "y", None),
            width=getattr(placement, "target_width", None),
            reason=reason,
            override_output=override_output,
        )

        # Ausführen
        try:
            out = svc.sign_pdf(
                input_path=input_path,
                placement=placement,
                reason=reason,
                enforce_label_positions=enforce_label_positions,
                override_label_offsets=override_label_offsets,
                override_font_sizes=override_font_sizes,
                override_output=override_output,
            )
            self._log("APISignSuccess", output_path=out)
            return out
        except Exception as ex:
            self._log("APISignFailed", error=str(ex))
            raise

    # ---------------- convenience API ----------------
    def sign_file_simple(
        self,
        *,
        input_path: str,
        page: int,
        x: float,
        y: float,
        width: float,
        name_pos: Union[str, "LabelPosition"] = "above",
        date_pos: Union[str, "LabelPosition"] = "below",
        name_offset: float = 6.0,
        date_offset: float = 18.0,
        x_offset: float = 0.0,
        font_sizes: Tuple[int, int] = (12, 12),
        password: Optional[str] = None,
        ignore_password_policy: bool = False,
        override_output: Optional[str] = None,
        reason: Optional[str] = "auto",
    ) -> str:
        """
        Vereinfachter Einstieg ohne Model-Imports im Caller.
        Koordinaten in PDF-Punkten; (x,y) = linke/untere Ecke der Signatur.
        """
        from signature.models.signature_enums import LabelPosition  # lazy
        from signature.models.signature_placement import SignaturePlacement  # lazy
        from signature.models.label_offsets import LabelOffsets  # lazy

        # Normalisieren
        if isinstance(name_pos, str):
            name_pos = LabelPosition(name_pos.lower())
        if isinstance(date_pos, str):
            date_pos = LabelPosition(date_pos.lower())

        placement = SignaturePlacement(page_index=int(page), x=float(x), y=float(y), target_width=float(width))
        offsets = LabelOffsets(
            name_above=(name_offset if name_pos == LabelPosition.ABOVE else 6.0),
            name_below=(name_offset if name_pos == LabelPosition.BELOW else 12.0),
            date_above=(date_offset if date_pos == LabelPosition.ABOVE else 18.0),
            date_below=(date_offset if date_pos == LabelPosition.BELOW else 24.0),
            x_offset=float(x_offset),
        )

        # Begleit-Logging
        self._log(
            "APISignSimpleStart",
            input_path=input_path,
            page=page,
            x=x,
            y=y,
            width=width,
            name_pos=getattr(name_pos, "value", str(name_pos)),
            date_pos=getattr(date_pos, "value", str(date_pos)),
            name_offset=name_offset,
            date_offset=date_offset,
            x_offset=x_offset,
            reason=reason,
            override_output=override_output,
        )

        return self.sign_pdf(
            input_path=input_path,
            placement=placement,
            reason=reason,
            enforce_label_positions=(name_pos, date_pos),
            override_label_offsets=offsets,
            override_font_sizes=font_sizes,
            password=password,
            ignore_password_policy=ignore_password_policy,
            override_output=override_output,
        )
