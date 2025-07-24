"""
settings_repository.py

Low-level SQLite access for module/user settings.

Table:
    settings(
        id INTEGER PK,
        scope TEXT NOT NULL,        -- 'global' | 'user'
        user_id INTEGER,            -- NULL for global
        module TEXT NOT NULL,
        key TEXT NOT NULL,
        value TEXT
        UNIQUE(scope, user_id, module, key)
    )
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

from core.config.config_loader import config_loader



class SettingsRepository:
    """CRUD helper for the settings table."""
    db_path = config_loader.get_qm_db_path()
    def __init__(self) -> None:

        self._ensure_table()

    # ---------------------------- CRUD -------------------------------- #
    def get(self, scope: str, module: str, key: str,
            user_id: Optional[int] = None) -> Optional[Any]:
        sql = """SELECT value FROM settings
                 WHERE scope=? AND module=? AND key=? AND user_id IS ?"""
        row = self._conn().execute(sql, (scope, module, key, user_id)).fetchone()
        return json.loads(row[0]) if row else None

    def set(
            self,
            scope: str,
            user_id: Optional[int],
            module: str,
            key: str,
            value: Any,
    ) -> None:
        """Insert or update a setting (atomic)."""
        val_json = json.dumps(value)
        sql = """
            INSERT INTO settings (scope, user_id, module, key, value)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(scope, user_id, module, key)
            DO UPDATE SET value = excluded.value
        """

        conn = self._conn()  # ← EIN Verbinder
        try:
            conn.execute(sql, (scope, user_id, module, key, val_json))
            conn.commit()
        finally:
            conn.close()  # ← sauber freigeben

    def get_module_settings(self, scope: str, module: str,
                            user_id: Optional[int] = None) -> Dict[str, Any]:
        sql = """SELECT key, value FROM settings
                 WHERE scope=? AND module=? AND user_id IS ?"""
        cur = self._conn().execute(sql, (scope, module, user_id))
        return {k: json.loads(v) for k, v in cur.fetchall()}

    # ---------------------------- intern ------------------------------ #
    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_table(self) -> None:
        with self._conn() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS settings (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       scope TEXT NOT NULL CHECK(scope IN ('global','user')),
                       user_id INTEGER,
                       module TEXT NOT NULL,
                       key TEXT NOT NULL,
                       value TEXT,
                       UNIQUE(scope, user_id, module, key)
                   )"""
            )
