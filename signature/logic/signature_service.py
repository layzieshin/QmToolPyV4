# signature/logic/signature_service.py
from __future__ import annotations
import hashlib, io, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Callable, Tuple

from PIL import Image, ImageDraw
from core.settings.logic.settings_manager import SettingsManager

# NOTE: models are sibling to "logic", so we must go one package UP:
from ..models.signature_config import SignatureConfig
from ..models.signature_enums import LabelPosition, OutputNamingMode, AdminPasswordPolicy
from ..models.signature_placement import SignaturePlacement
from ..models.label_offsets import LabelOffsets

# logic-local modules correctly use single-dot relative imports
from .naming_strategy import DefaultSuffixStrategy, NamingStrategy, NamingContext
from .encryption import encrypt_bytes, decrypt_bytes
from .pdf_signer import PdfSigner, RenderLabels
from cryptography.fernet import InvalidToken

_FEATURE_ID = "core_signature"


def _hex_to_rgb(hexstr: str) -> Tuple[int, int, int]:
    """
    Convert hex color (#RRGGBB or #RGB) into an RGB tuple for PIL.
    """
    s = (hexstr or "#000000").strip()
    if not s.startswith("#"):
        s = "#" + s
    if len(s) == 4:
        r = int(s[1] * 2, 16); g = int(s[2] * 2, 16); b = int(s[3] * 2, 16)
    else:
        r = int(s[1:3], 16); g = int(s[3:5], 16); b = int(s[5:7], 16)
    return (r, g, b)


class SignatureService:
    """
    Core signing logic (no UI). AppContext is imported lazily to avoid hard coupling.

    All settings are read/written through SettingsManager under feature id "core_signature".
    User-scoped settings are applied when AppContext.current_user is available.
    """

    # -------- Context --------------------------------------------------------
    @staticmethod
    def _ctx():
        try:
            from core.common.app_context import AppContext  # noqa
            return AppContext
        except Exception:
            return None

    # -------- Construction ---------------------------------------------------
    def __init__(self, *, settings_manager: SettingsManager,
                 logger: Optional[Any] = None,
                 naming_registry: Optional[dict[str, NamingStrategy]] = None,
                 password_verifier: Optional[Callable[[str, str], bool]] = None) -> None:
        self._sm = settings_manager
        self._logger = logger
        self._password_verifier = password_verifier
        self._strategies: dict[str, NamingStrategy] = {"default_suffix": DefaultSuffixStrategy()}
        if naming_registry:
            self._strategies.update(naming_registry)

        # Persisted base directory for encrypted signature blobs
        base_dir = Path(self._sm.get(_FEATURE_ID, "data_dir", str(Path("data") / "signatures")))
        base_dir.mkdir(parents=True, exist_ok=True)
        self._base_dir = base_dir
        self._sm.set(_FEATURE_ID, "data_dir", str(base_dir))  # keep canonicalized path

    # -------- Internal helpers ----------------------------------------------
    def _persist_settings(self) -> None:
        """
        Best-effort flush for diverse SettingsManager implementations.
        """
        for meth in ("persist", "save", "flush"):
            fn = getattr(self._sm, meth, None)
            if callable(fn):
                try:
                    fn()
                    break
                except Exception:
                    pass

    # -------- Admin: global label defaults ----------------------------------
    def load_global_offset_defaults(self) -> LabelOffsets:
        g = lambda k, d: self._sm.get(_FEATURE_ID, f"g_{k}", d)
        return LabelOffsets(
            name_above=float(g("name_above", 6.0)),
            name_below=float(g("name_below", 12.0)),
            date_above=float(g("date_above", 18.0)),
            date_below=float(g("date_below", 24.0)),
            x_offset=float(g("x_offset", 0.0)),
        )

    def save_global_offset_defaults(self, offsets: LabelOffsets) -> None:
        self._sm.set(_FEATURE_ID, "g_name_above", float(offsets.name_above))
        self._sm.set(_FEATURE_ID, "g_name_below", float(offsets.name_below))
        self._sm.set(_FEATURE_ID, "g_date_above", float(offsets.date_above))
        self._sm.set(_FEATURE_ID, "g_date_below", float(offsets.date_below))
        self._sm.set(_FEATURE_ID, "g_x_offset", float(offsets.x_offset))
        self._persist_settings()

    # -------- User-scoped config --------------------------------------------
    def load_config(self) -> SignatureConfig:
        ctx = self._ctx()
        user = getattr(ctx, "current_user", None) if ctx else None
        uid = getattr(user, "id", None)

        gdef = self.load_global_offset_defaults()

        def get_user(k: str, d):
            if uid:
                return self._sm.get(_FEATURE_ID, k, d, user_specific=True, user_id=uid)
            return self._sm.get(_FEATURE_ID, k, d)

        def get_global(k: str, d):
            return self._sm.get(_FEATURE_ID, k, d)

        off = LabelOffsets(
            name_above=float(get_user("name_above", gdef.name_above)),
            name_below=float(get_user("name_below", gdef.name_below)),
            date_above=float(get_user("date_above", gdef.date_above)),
            date_below=float(get_user("date_below", gdef.date_below)),
            x_offset=float(get_user("x_offset", gdef.x_offset)),
        )

        # Accept "off" if previously saved (backward compatibility)
        def _lp(val: str, default: LabelPosition) -> LabelPosition:
            try:
                return LabelPosition(val)
            except Exception:
                return default

        return SignatureConfig(
            stroke_width=int(get_user("stroke_width", 3)),
            embed_name=bool(get_user("embed_name", True)),
            embed_date=bool(get_user("embed_date", True)),
            name_position=_lp(get_user("name_position", "above"), LabelPosition.ABOVE),
            date_position=_lp(get_user("date_position", "below"), LabelPosition.BELOW),
            date_format=str(get_user("date_format", "%Y-%m-%d %H:%M")),
            label_offsets=off,
            label_color=str(get_user("label_color", "#000000")),
            name_font_size=int(get_user("name_font_size", 12)),
            date_font_size=int(get_user("date_font_size", 12)),
            naming_mode=OutputNamingMode(get_user("naming_mode", "default_suffix")),
            external_strategy_id=get_user("external_strategy_id", None),
            user_pwd_required=bool(get_user("user_pwd_required", True)),
            admin_password_policy=AdminPasswordPolicy(get_global("admin_password_policy", "user_specific")),
        )

    def save_config(self, cfg: SignatureConfig) -> None:
        ctx = self._ctx()
        user = getattr(ctx, "current_user", None) if ctx else None
        uid = getattr(user, "id", None)

        def set_user(k: str, v):
            if uid:
                self._sm.set(_FEATURE_ID, k, v, user_specific=True, user_id=uid)
            else:
                self._sm.set(_FEATURE_ID, k, v)

        set_user("stroke_width", cfg.stroke_width)
        set_user("embed_name", cfg.embed_name)
        set_user("embed_date", cfg.embed_date)
        set_user("name_position", cfg.name_position.value)
        set_user("date_position", cfg.date_position.value)
        set_user("date_format", cfg.date_format)
        set_user("name_above", float(cfg.label_offsets.name_above))
        set_user("name_below", float(cfg.label_offsets.name_below))
        set_user("date_above", float(cfg.label_offsets.date_above))
        set_user("date_below", float(cfg.label_offsets.date_below))
        set_user("x_offset", float(cfg.label_offsets.x_offset))
        set_user("label_color", cfg.label_color)
        set_user("name_font_size", int(cfg.name_font_size))
        set_user("date_font_size", int(cfg.date_font_size))
        set_user("naming_mode", cfg.naming_mode.value)
        set_user("external_strategy_id", cfg.external_strategy_id)
        set_user("user_pwd_required", cfg.user_pwd_required)

        self._sm.set(_FEATURE_ID, "admin_password_policy", cfg.admin_password_policy.value)
        self._persist_settings()

    # -------- Password policy -----------------------------------------------
    def is_password_required(self) -> bool:
        cfg = self.load_config()
        if cfg.admin_password_policy == AdminPasswordPolicy.ALWAYS:
            return True
        if cfg.admin_password_policy == AdminPasswordPolicy.NEVER:
            return False
        return bool(cfg.user_pwd_required)

    def verify_password(self, user_id: str, password: str) -> bool:
        """
        Try injected verifier, then auth providers exposed by AppContext, then bridge.
        Returns True as soon as any verifier accepts the credentials.
        """
        if callable(self._password_verifier):
            try:
                if bool(self._password_verifier(user_id, password)):
                    return True
            except Exception:
                pass

        ctx = self._ctx()
        user = getattr(ctx, "current_user", None) if ctx else None
        uname = getattr(user, "username", None) or getattr(user, "name", None)

        # Try AppContext.auth.verify_password (positional and keyword variants)
        try:
            auth = getattr(ctx, "auth", None) if ctx else None
            if auth and hasattr(auth, "verify_password"):
                fn = getattr(auth, "verify_password")
                for args in ((user_id, password), (uname, password) if uname else None, (password,)):
                    if args is None:
                        continue
                    try:
                        if bool(fn(*args)):
                            return True
                    except TypeError:
                        try:
                            if bool(fn(user_id=user_id, password=password)):
                                return True
                        except Exception:
                            try:
                                if uname and bool(fn(username=uname, password=password)):
                                    return True
                            except Exception:
                                pass
        except Exception:
            pass

        # Try AppContext.verify_password
        try:
            if ctx and hasattr(ctx, "verify_password"):
                fn2 = getattr(ctx, "verify_password")
                for args in ((user_id, password), (uname, password) if uname else None, (password,)):
                    if args is None:
                        continue
                    try:
                        if bool(fn2(*args)):
                            return True
                    except TypeError:
                        try:
                            if bool(fn2(user_id=user_id, password=password)):
                                return True
                        except Exception:
                            try:
                                if uname and bool(fn2(username=uname, password=password)):
                                    return True  # <= missing 'return' fixed
                            except Exception:
                                pass
        except Exception:
            pass

        # Try bridge (optional)
        try:
            from usermanagement.logic.auth_bridge import verify_password as bridge_verify
            if bool(bridge_verify(user_id=int(user_id) if user_id is not None else None,
                                  username=uname, password=password)):
                return True
        except Exception:
            pass

        return False

    # -------- Encrypted signature store -------------------------------------
    def _sig_path(self, user_id: str) -> Path:
        """Internal canonical path builder for a user's encrypted signature file."""
        return self._base_dir / f"{user_id}.sig"

    def _user_sig_path(self, user_id: str) -> Path:
        """
        Backward-compatible alias for older code paths.

        Some callers used `_user_sig_path(...)`. Keep this thin alias to avoid
        AttributeError when UI code still calls it.
        """
        return self._sig_path(user_id)

    def save_user_signature_png(self, user_id: str, png_bytes: bytes) -> None:
        """
        Encrypt and persist the user's signature PNG as {base_dir}/{user_id}.sig.
        """
        token = encrypt_bytes(self._sm, png_bytes)
        self._sig_path(user_id).write_bytes(token)
        self._persist_settings()

    def load_user_signature_png(self, user_id: str) -> bytes | None:
        """
        Load and decrypt the user's signature PNG.
        Returns None if not present OR if decryption fails (graceful degrade).
        """
        p = self._user_sig_path(user_id)
        if not p.exists():
            return None
        raw = p.read_bytes()
        try:
            return decrypt_bytes(self._sm, raw)
        except InvalidToken:
            # treat as "no signature", optionally log
            try:
                if self._logger and hasattr(self._logger, "log"):
                    self._logger.log(feature="SignatureService", event="InvalidToken",
                                     message=f"Cannot decrypt {p}")
            except Exception:
                pass
            return None

    def delete_user_signature(self, user_id: str) -> bool:
        p = self._sig_path(user_id)
        if p.exists():
            p.unlink()
            self._persist_settings()
            return True
        return False

    # -------- Canvas strokes -> PNG -----------------------------------------
    def render_png_from_strokes(self, strokes: list[list[tuple[int, int]]],
                                size: tuple[int, int], stroke_width: int,
                                name_text: Optional[str] = None, date_text: Optional[str] = None,
                                name_pos: LabelPosition = LabelPosition.ABOVE,
                                date_pos: LabelPosition = LabelPosition.BELOW) -> bytes:
        """
        Convert freehand strokes (from UI) into a transparent PNG.
        """
        w, h = size
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        drw = ImageDraw.Draw(img)
        for poly in strokes:
            if len(poly) >= 2:
                drw.line(poly, fill=(0, 0, 0, 255), width=stroke_width, joint="curve")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    # -------- Signing --------------------------------------------------------
    def _audit(self, payload: dict) -> None:
        """
        Append a JSON line with a signing event to signature_audit.log.
        Falls back silently if logger is not available.
        """
        payload["ts_utc"] = datetime.now(timezone.utc).isoformat()
        try:
            if self._logger and hasattr(self._logger, "log"):
                self._logger.log(feature="Signature", event="sign_pdf",
                                 reference=payload.get("input_path"), data=payload)
                return
        except Exception:
            pass
        (self._base_dir / "signature_audit.log").open("a", encoding="utf-8") \
            .write(json.dumps(payload, ensure_ascii=False) + "\n")

    def sign_pdf(self, input_path: str, placement: SignaturePlacement, *,
                 override_output: Optional[str] = None, reason: Optional[str] = None,
                 use_user_signature: bool = True, raw_signature_png: Optional[bytes] = None,
                 enforce_label_positions: Optional[tuple[LabelPosition, LabelPosition]] = None,
                 override_label_offsets: Optional[LabelOffsets] = None,
                 override_font_sizes: Optional[tuple[int, int]] = None) -> str:
        """
        Apply the signature image and optional labels to a PDF and return the output path.
        """
        ctx = self._ctx()
        user = getattr(ctx, "current_user", None) if ctx else None
        uid = getattr(user, "id", None)
        display_name = (getattr(user, "full_name", None)
                        or getattr(user, "name", None)
                        or getattr(user, "username", None))
        if not uid:
            raise RuntimeError("No current user; signing requires authentication.")

        cfg = self.load_config()

        sig: Optional[bytes] = None
        if use_user_signature:
            sig = self.load_user_signature_png(uid)
            if not sig and not raw_signature_png:
                raise RuntimeError("No stored signature for user.")
        if raw_signature_png:
            sig = raw_signature_png
        if sig is None:
            raise RuntimeError("Signature image not available.")

        name_pos, date_pos = cfg.name_position, cfg.date_position
        if enforce_label_positions:
            name_pos, date_pos = enforce_label_positions

        name_fs = max(6, int(override_font_sizes[0])) if override_font_sizes else max(6, int(cfg.name_font_size))
        date_fs = max(6, int(override_font_sizes[1])) if override_font_sizes else max(6, int(cfg.date_font_size))

        # Respect OFF: if OFF, pass None (PdfSigner will skip)
        name_text = (display_name if cfg.embed_name and display_name and name_pos != LabelPosition.OFF else None)
        date_text = (datetime.now().strftime(cfg.date_format) if cfg.embed_date and date_pos != LabelPosition.OFF else None)

        labels = RenderLabels(
            name_text=name_text,
            date_text=date_text,
            name_pos=name_pos,
            date_pos=date_pos,
            date_format=cfg.date_format,
            offsets=(override_label_offsets or cfg.label_offsets),
            color_rgb=_hex_to_rgb(cfg.label_color),
            name_font_size=name_fs,
            date_font_size=date_fs,
        )

        # Output path strategy
        if override_output:
            out_path = override_output
        else:
            if cfg.naming_mode == OutputNamingMode.EXTERNAL_STRATEGY and cfg.external_strategy_id:
                strat = self._strategies.get(cfg.external_strategy_id)
                if not strat:
                    raise RuntimeError(f"Unknown naming strategy '{cfg.external_strategy_id}'.")
            else:
                strat = self._strategies["default_suffix"]
            out_path = strat.propose_output_path(NamingContext(input_path=input_path, user_id=uid, reason=reason))

        PdfSigner.sign_pdf(input_path=input_path, output_path=out_path,
                           png_signature=sig, placement=placement, labels=labels)

        self._audit({
            "user_id": uid, "username": getattr(user, "username", None),
            "display_name": display_name, "input_path": input_path, "output_path": out_path,
            "page_index": placement.page_index, "x": placement.x, "y": placement.y, "width": placement.target_width,
            "embed_name": bool(cfg.embed_name), "embed_date": bool(cfg.embed_date),
            "name_position": name_pos.value, "date_position": date_pos.value,
            "date_format": cfg.date_format, "label_color": cfg.label_color,
            "name_font_size": name_fs, "date_font_size": date_fs,
            "label_offsets": {
                "name_above": labels.offsets.name_above, "name_below": labels.offsets.name_below,
                "date_above": labels.offsets.date_above, "date_below": labels.offsets.date_below,
                "x_offset": labels.offsets.x_offset
            },
            "signature_sha256": hashlib.sha256(sig).hexdigest(),
            "reason": reason,
        })
        return out_path
