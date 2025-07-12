"""
settings_manager.py

High-level API for global/user settings stored in SQLite.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.settings.logic.settings_repository import SettingsRepository


class SettingsManager:
    def __init__(self) -> None:
        self.repo = SettingsRepository()
        self._ensure_default_language()

    # ------------- NEW: default language ----------------------------- #
    def _ensure_default_language(self) -> None:
        """Insert global language=de once, if not present."""
        if self.repo.get("global", "app", "language", None) is None:
            self.repo.set("global", None, "app", "language", "de")

    # ---------------- public API ---------------- #
    def get(
        self,
        module: str,
        key: str,
        *,
        user_specific: bool = False,
        default: Any = None,
    ) -> Any:
        scope, uid = self._scope_user(user_specific)
        val = self.repo.get(scope, module, key, uid)
        return val if val is not None else default

    def set(
        self,
        module: str,
        key: str,
        value: Any,
        *,
        user_specific: bool = False,
    ) -> None:
        scope, uid = self._scope_user(user_specific)
        self.repo.set(scope, uid, module, key, value)  # <--- Reihenfolge!

    def all_for_module(
        self,
        module: str,
        *,
        user_specific: bool = False,
    ) -> Dict[str, Any]:
        scope, uid = self._scope_user(user_specific)
        return self.repo.get_module_settings(scope, module, uid)

    # ---------------- helpers ------------------- #
    @staticmethod
    def _scope_user(user_specific: bool) -> tuple[str, Optional[int]]:
        """
        Returns ("user", user_id) or ("global", None)
        without importing AppContext at module level.
        """
        if user_specific:
            # Lazy import *inside* the function to break circular dependency
            from core.common.app_context import AppContext  # noqa: WPS433
            if AppContext.current_user:
                return "user", AppContext.current_user.id
        return "global", None
