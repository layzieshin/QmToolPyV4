"""
core/settings/logic/settings_manager.py
=======================================

High-Level-API für Settings.
"""

from __future__ import annotations
from threading import RLock
from typing import Any, Final

from core.logging.logic.logger import logger
from core.settings.logic.settings_repository import SettingsRepository


class SettingsManager:
    _instance: "SettingsManager | None" = None
    _lock: Final[RLock] = RLock()

    def __new__(cls) -> "SettingsManager":  # noqa: D401
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._repo = SettingsRepository()
            return cls._instance

    # ------------------------------------------------------------------ #
    #  API                                                               #
    # ------------------------------------------------------------------ #
    def get(
        self,
        namespace: str,
        key: str,
        fallback: Any | None = None,
        *,
        user_specific: bool = False,
        user_id: str | None = None,
    ) -> Any | None:
        if user_specific and not user_id:
            logger.log("SettingsManager", "MissingUserID", message=f"{namespace}.{key}")
            return fallback
        return self._repo.get(namespace, key, user_id if user_specific else None, fallback)

    def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        *,
        user_specific: bool = False,
        user_id: str | None = None,
    ) -> None:
        if user_specific and not user_id:
            raise ValueError("user_id muss gesetzt sein, wenn user_specific=True")
        self._repo.set(namespace, key, value, user_id if user_specific else None)
        logger.log("SettingsManager", "Set", message=f"{namespace}.{key}")

    def delete(
        self,
        namespace: str,
        key: str,
        *,
        user_specific: bool = False,
        user_id: str | None = None,
    ) -> None:
        self._repo.delete(namespace, key, user_id if user_specific else None)


# Globale Instanz
settings_manager: SettingsManager = SettingsManager()  # pylint: disable=invalid-name
