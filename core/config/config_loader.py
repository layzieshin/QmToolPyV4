"""
Backward-compatible wrapper delegating to :mod:`config_service`.

Existing callers can keep using :class:`ConfigLoader` while the new
:class:`ConfigService` provides layered, typed configuration handling.
"""
from __future__ import annotations

from pathlib import Path
from threading import RLock

from .config_service import ConfigService, config_service


class ConfigLoader:
    """Thin wrapper around :class:`ConfigService` (legacy API)."""

    _instance: "ConfigLoader | None" = None
    _lock = RLock()

    def __new__(cls) -> "ConfigLoader":  # noqa: D401
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._service = config_service
            return cls._instance

    # ------------------------------------------------------------------ #
    #  Delegated getters
    # ------------------------------------------------------------------ #
    def get_qm_db_path(self) -> Path:
        return self._service.database.qm_tool

    def get_logging_db_path(self) -> Path:
        return self._service.database.logging

    def get_app_name(self) -> str:
        return self._service.general.app_name

    def get_version(self) -> str:
        return self._service.general.version

    def get_modules_json_path(self) -> Path:
        return self._service.files.modules_json

    def get_labels_tsv_path(self) -> Path:
        return self._service.files.labels_tsv


# Global convenience accessors
config_loader: ConfigLoader = ConfigLoader()  # pylint: disable=invalid-name
QM_DB_PATH: Path = config_loader.get_qm_db_path()
LOG_DB_PATH: Path = config_loader.get_logging_db_path()
MODULES_JSON_PATH = config_loader.get_modules_json_path()
LABELS_TSV_PATH = config_loader.get_labels_tsv_path()
