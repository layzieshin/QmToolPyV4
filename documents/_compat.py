"""
Compatibility shim so the module can load even if some core.* types
are not present or named slightly differently.

- Tries to import your real classes first.
- Falls back to minimal stubs that keep the UI usable.
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Optional

# ---- AppContext & i18n ------------------------------------------------------
try:
    from core.common.app_context import AppContext as _RealAppContext, T as _RealT  # type: ignore
    AppContext = _RealAppContext  # re-export
    T = _RealT                    # re-export
except Exception:
    class AppContext:  # minimal stub
        app_storage_dir: str = os.path.join(os.getcwd(), "data")
        current_user: object | None = None
    def T(key: str) -> Optional[str]:
        return None

# ---- SettingsManager ---------------------------------------------------------
try:
    from core.settings.logic.settings_manager import SettingsManager as _RealSettingsManager  # type: ignore
    SettingsManager = _RealSettingsManager
except Exception:
    class SettingsManager:  # in-memory stub
        def __init__(self) -> None:
            self._d: dict[str, dict[str, object]] = {}
        def get(self, feature: str, key: str, default: object | None = None) -> object | None:
            return self._d.get(feature, {}).get(key, default)
        def set(self, feature: str, key: str, value: object) -> None:
            self._d.setdefault(feature, {})[key] = value

# ---- Licensing ---------------------------------------------------------------
try:
    from core.contracts.licensable import Licensable as _RealLicensable, LicenseState as _RealLicenseState  # type: ignore
    Licensable = _RealLicensable
    LicenseState = _RealLicenseState
except Exception:
    @dataclass
    class LicenseState:
        enabled: bool = True
    class Licensable:
        def license_feature_id(self) -> str: return "documents"
        def apply_license_state(self, state: LicenseState) -> None: pass
        def is_access_allowed(self) -> bool: return True

try:
    from core.contracts.licensing_service import LicensingService as _RealLicensingService  # type: ignore
    LicensingService = _RealLicensingService
except Exception:
    class LicensingService:  # structural only
        def get_state(self, feature_id: str) -> LicenseState: return LicenseState(True)

# ---- Signature ---------------------------------------------------------------
try:
    from core.contracts.signable import (  # type: ignore
        Signable as _RealSignable,
        SignRequest as _RealSignRequest,
        SignResult as _RealSignResult,
        SignState as _RealSignState
    )
    Signable = _RealSignable
    SignRequest = _RealSignRequest
    SignResult = _RealSignResult
    SignState = _RealSignState
except Exception:
    from dataclasses import dataclass
    class SignState:
        NOT_SIGNED = "NOT_SIGNED"
        PENDING = "PENDING"
        SIGNED = "SIGNED"
        FAILED = "FAILED"
    @dataclass
    class SignRequest:
        user_id: str
        reason: str | None
        signature: bytes | None
    @dataclass
    class SignResult:
        success: bool
        state: str
        message: str = ""
    class Signable:
        def is_signing_enabled(self, user_id: Optional[str]) -> bool: return False
        def get_sign_state(self, user_id: Optional[str]) -> str: return SignState.NOT_SIGNED
        def request_sign(self, req: SignRequest) -> SignResult: return SignResult(False, SignState.FAILED, "Not implemented")
