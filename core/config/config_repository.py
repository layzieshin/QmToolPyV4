"""
core/config/config_repository.py
================================

Low-Level key-value configuration storage based on SQLite.

• Uses the new ConfigLoader to obtain correct database paths.
• Can be used as a central store for runtime settings, feature flags, UI prefs, …

Note: Primary application settings (DB paths, app name, …) live in
      <root>/databases/config.ini and are read-only via ConfigLoader.
      This repository complements them with modifiable runtime values.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

# Public getters from ConfigLoader
from core.config.config_loader import config_loader


class ConfigRepository:
    """
    Thread-safe singleton for key-value configs stored in SQLite.

    DB schema
    ---------
    CREATE TABLE config (
        section TEXT NOT NULL,
        key     TEXT NOT NULL,
        value   TEXT,
        PRIMARY KEY (section, key)
    )
    """

    _instances: dict[Path, "ConfigRepository"] = {}
    _lock = threading.Lock()

    # ------------------------------------------------------------------ #
    #  Construction / instantiation
    # ------------------------------------------------------------------ #
    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            db_path = config_loader.get_qm_db_path()

        self.db_path = db_path
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row

        self._ensure_table()
        self._defaults: dict[str, dict[str, Any]] = {
            "Database": {
                "qm_tool": str(config_loader.get_qm_db_path().as_posix()),
                "logging": str(config_loader.get_logging_db_path().as_posix()),
            },
            "General": {
                "app_name": config_loader.get_app_name(),
                "version": config_loader.get_version(),
            },
            "Files": {
                "modules_json": str(config_loader.get_modules_json_path().as_posix()),
                "labels_tsv": str(config_loader.get_labels_tsv_path().as_posix()),
            },
        }
        self._inject_defaults()

    # ------------------------------------------------------------------ #
    #  Singleton accessor
    # ------------------------------------------------------------------ #
    @classmethod
    def instance(cls, db_path: Path | None = None) -> "ConfigRepository":
        """
        Returns the singleton instance for *db_path* (default: qm_tool.db).

        Example
        -------
        >>> repo = ConfigRepository.instance()
        >>> other = ConfigRepository.instance()       # same object
        >>> assert repo is other
        """
        if db_path is None:
            db_path = config_loader.get_qm_db_path()

        with cls._lock:
            if db_path not in cls._instances:
                cls._instances[db_path] = cls(db_path)
            return cls._instances[db_path]

    # ------------------------------------------------------------------ #
    #  DB setup
    # ------------------------------------------------------------------ #
    def _ensure_table(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS config (
                section TEXT NOT NULL,
                key     TEXT NOT NULL,
                value   TEXT,
                PRIMARY KEY (section, key)
            )
            """
        )
        self._conn.commit()

    def _inject_defaults(self) -> None:
        """Writes default values if they are missing."""
        for section, items in self._defaults.items():
            for key, value in items.items():
                if self.get(section, key) is None:
                    self.set(section, key, value)

    # ------------------------------------------------------------------ #
    #  Public CRUD helpers
    # ------------------------------------------------------------------ #
    def get(self, section: str, key: str, fallback: Any = None) -> str | None:
        """
        Returns the value for *section/key* or *fallback* if not set.

        Example
        -------
        >>> repo = ConfigRepository.instance()
        >>> repo.get("General", "app_name", "<unnamed>")
        '<unnamed>'
        """
        cur = self._conn.cursor()
        cur.execute(
            "SELECT value FROM config WHERE section=? AND key=?", (section, key)
        )
        row = cur.fetchone()
        return row["value"] if row else fallback

    def get_bool(self, section: str, key: str, fallback: bool = False) -> bool:
        """
        Returns the value as `bool`.

        Truthy strings: "true", "1", "yes" (case-insensitive).

        Example
        -------
        >>> repo = ConfigRepository.instance()
        >>> repo.set("Features", "dark_mode", "true")
        >>> repo.get_bool("Features", "dark_mode")
        True
        """
        val = self.get(section, key, fallback)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.strip().lower() in ("true", "1", "yes")
        return bool(val)

    def get_int(self, section: str, key: str, fallback: int = 0) -> int:
        """
        Returns the value as `int`, else *fallback*.

        Example
        -------
        >>> repo = ConfigRepository.instance()
        >>> repo.set("UI", "window_width", 1024)
        >>> repo.get_int("UI", "window_width")
        1024
        """
        val = self.get(section, key, fallback)
        try:
            return int(val)
        except (TypeError, ValueError):
            return fallback

    def set(self, section: str, key: str, value: Any) -> None:
        """
        Inserts or updates *section/key* with *value*.

        Example
        -------
        >>> repo = ConfigRepository.instance()
        >>> repo.set("General", "app_name", "QM-Tool Deluxe")
        """
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO config (section, key, value)
            VALUES (?, ?, ?)
            ON CONFLICT(section, key) DO UPDATE SET value=excluded.value
            """,
            (section, key, str(value)),
        )
        self._conn.commit()
