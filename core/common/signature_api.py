# core/common/signature_api.py
from __future__ import annotations

from typing import Optional, Tuple, Union

from core.settings.logic.settings_manager import SettingsManager

# Fallback-Logger (falls AppContext.logger fehlt)
try:
    from core.logging.logic.logger import logger as default_logger  # type: ignore
except Exception:
    default_logger = None  # type: ignore

from signature.logic.signature_service import SignatureService
from signature.models.signature_placement import SignaturePlacement
from signature.models.label_offsets import LabelOffsets
from signature.models.signature_enums import LabelPosition


class SignatureAPI:
    """
    Thin facade around SignatureService, designed for global use via AppContext.signature.

    Änderungen zur Vermeidung von Zirkularimporten:
      - KEIN Top-Level-Import von AppContext oder T mehr.
      - AppContext & T werden NUR innerhalb von Methoden (lazy) importiert.
      - Logging & i18n weiter integriert.

    Nutzung in anderen Modulen:
        from core.common.app_context import AppContext
        AppContext.signature.sign_file_simple(...)
    """

    def __init__(self) -> None:
        self._svc: Optional[SignatureService] = None

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

    def _get_service(self) -> SignatureService:
        """Lazy Initialisierung des SignatureService mit Settings/Logger aus dem AppContext."""
        if self._svc is not None:
            return self._svc

        ctx = self._ctx()
        sm = getattr(ctx, "settings_manager", None) if ctx else None
        if sm is None:
            sm = SettingsManager()
            # zurück in den Kontext cachen, falls möglich
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

    # ---------------- helpers for caller modules ----------------
    def has_signature(self) -> bool:
        """True, wenn der aktuelle Benutzer eine gespeicherte Signatur hat."""
        ctx = self._ctx()
        user = getattr(ctx, "current_user", None) if ctx else None
        uid = getattr(user, "id", None)
        if uid is None:
            return False
        return self._get_service().load_user_signature_png(uid) is not None  # type: ignore[arg-type]

    def ensure_signature_or_raise(self) -> None:
        """RuntimeError, wenn keine gespeicherte Signatur vorhanden ist (mit i18n & Logging)."""
        if not self.has_signature():
            self._log("EnsureSignatureMissing")
            msg = self._t("core_signature.api.no_signature") or "No stored signature for current user."
            raise RuntimeError(msg)

    # ---------------- primary API ----------------
    def sign_pdf(
        self,
        *,
        input_path: str,
        placement: SignaturePlacement,
        reason: Optional[str] = "auto",
        enforce_label_positions: Optional[Tuple[LabelPosition, LabelPosition]] = None,
        override_label_offsets: Optional[LabelOffsets] = None,
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
            page=placement.page_index,
            x=placement.x,
            y=placement.y,
            width=placement.target_width,
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
        name_pos: Union[str, LabelPosition] = "above",
        date_pos: Union[str, LabelPosition] = "below",
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
            name_pos=name_pos.value,
            date_pos=date_pos.value,
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
