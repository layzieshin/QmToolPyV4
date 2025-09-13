"""core/config/config_loader.py
============================

Backwards compatible facade for configuration values.

Historically the application used ``ConfigLoader`` to read values from a
``config.ini`` file.  The new :mod:`core.config.config_service` provides a
layered, typed configuration system.  This module keeps the old API
intact while delegating all lookups to the new service.
"""

from __future__ import annotations

from pathlib import Path
from threading import RLock

from .config_service import config_service


class ConfigLoader:
    """Thread-safe singleton delegating to :class:`ConfigService`."""

    _instance: "ConfigLoader | None" = None
    _lock = RLock()

    def __new__(cls) -> "ConfigLoader":  # noqa: D401
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    # ------------------------------------------------------------------
    #  Delegated getters
    # ------------------------------------------------------------------
    def get_qm_db_path(self) -> Path:
        return config_service.database.qm_tool

    def get_logging_db_path(self) -> Path:
        return config_service.database.logging

    def get_app_name(self) -> str:
        return config_service.general.app_name

    def get_version(self) -> str:
        return config_service.general.version

    def get_modules_json_path(self) -> Path:
        return config_service.files.modules_json

    def get_labels_tsv_path(self) -> Path:
        return config_service.files.labels_tsv


# ---------------------------------------------------------------------------
#  Global instance for convenience
# ---------------------------------------------------------------------------
config_loader: ConfigLoader = ConfigLoader()  # pylint: disable=invalid-name
QM_DB_PATH: Path = config_loader.get_qm_db_path()
LOG_DB_PATH: Path = config_loader.get_logging_db_path()
MODULES_JSON_PATH = config_loader.get_modules_json_path()
LABELS_TSV_PATH = config_loader.get_labels_tsv_path()

