"""
===============================================================================
Base SQLite Repository – connection helper
-------------------------------------------------------------------------------
Purpose:
    Provide a tiny helper to obtain a SQLite connection with common options:
    - row_factory = sqlite3.Row
    - PRAGMA foreign_keys = ON

Integration:
    - Concrete repositories inherit from this class and use `self.conn`.
    - DB path is read from the host config (QM_DB_PATH); falls back to
      'qmtool.db' for isolated development.

Notes:
    - This class does not manage migrations beyond simple DDL in child repos.
===============================================================================
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Optional

try:
    # Host project config path (preferred source of truth)
    from core.config.config_loader import QM_DB_PATH  # type: ignore
except Exception:  # pragma: no cover
    QM_DB_PATH = Path("qmtool.db")


class BaseSQLiteRepo:
    """
    Thin base to share connection handling across SQLite repositories.

    Properties
    ----------
    conn : sqlite3.Connection
        Lazily created connection with foreign keys enforced and Row factory.

    Methods
    -------
    close() -> None
        Close the connection (idempotent); next access to 'conn' recreates it.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = Path(db_path) if db_path else Path(QM_DB_PATH)
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Return a shared sqlite3.Connection; create it on first use."""
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    def close(self) -> None:
        """Close the current connection if present and clear the handle."""
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None
