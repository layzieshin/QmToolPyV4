"""
core/licensing/logic/license_repository.py

SQLite persistence for licenses.
Table 'licenses':
- tag TEXT PRIMARY KEY
- payload TEXT        (e.g., signed key, token, etc.)
"""

from __future__ import annotations
from typing import Optional
from core.config.config_loader import QM_DB_PATH
from core.common.db_interface import SQLiteRepository


class LicenseRepository(SQLiteRepository):
    """Minimal license storage; extend as needed."""

    def __init__(self) -> None:
        super().__init__(QM_DB_PATH, check_same_thread=False)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS licenses(
                tag TEXT PRIMARY KEY,
                payload TEXT
            )
            """
        )
        self.conn.commit()

    def has(self, tag: str) -> bool:
        row = self.conn.execute("SELECT tag FROM licenses WHERE tag=?", (tag,)).fetchone()
        return row is not None

    def get(self, tag: str) -> Optional[str]:
        row = self.conn.execute("SELECT payload FROM licenses WHERE tag=?", (tag,)).fetchone()
        return row[0] if row else None

    def set(self, tag: str, payload: str) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO licenses(tag, payload) VALUES(?, ?)
                ON CONFLICT(tag) DO UPDATE SET payload=excluded.payload
                """,
                (tag, payload),
            )

    def delete(self, tag: str) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM licenses WHERE tag=?", (tag,))
