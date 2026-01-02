"""SQLite implementation of DatabaseAdapter.

Uses core. common.db_interface for connection management.
"""

from __future__ import annotations
from typing import Any, List, Dict, Optional
from pathlib import Path
import sqlite3

from documents.adapters.database_adapter import DatabaseAdapter
from core.common.db_interface import create_sqlite_connection


class SQLiteAdapter(DatabaseAdapter):
    """SQLite implementation of DatabaseAdapter."""

    def __init__(self, db_path: str | Path):
        """
        Initialize SQLite adapter.

        Args:
            db_path: Path to SQLite database file
        """
        self._db_path = Path(db_path)
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Get or create connection."""
        if self._conn is None:
            self._conn = create_sqlite_connection(
                self._db_path,
                check_same_thread=False,
                foreign_keys=True
            )
        return self._conn

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute query and return cursor."""
        return self.conn.execute(query, params)

    def fetchone(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Fetch single row as dictionary."""
        row = self.conn.execute(query, params).fetchone()
        return dict(row) if row else None

    def fetchall(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Fetch all rows as list of dictionaries."""
        rows = self.conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def insert(self, table: str, data: Dict[str, Any]) -> int:
        """Insert row and return last inserted ID."""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["? "] * len(data))
        values = tuple(data.values())

        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        cursor = self.conn.execute(query, values)
        self.commit()  # <-- WICHTIG!

        return cursor.lastrowid

    def update(self, table: str, data: Dict[str, Any], where: str, where_params: tuple = ()) -> int:
        """Update rows and return count of affected rows."""
        set_clause = ", ".join([f"{key} = ?" for key in data.keys()])
        params = tuple(data.values()) + tuple(where_params)

        query = f"UPDATE {table} SET {set_clause} WHERE {where}"
        cursor = self.conn.execute(query, params)
        self.commit()

        return cursor.rowcount

    def delete(self, table: str, where: str, where_params: tuple = ()) -> int:
        """Delete rows and return count of affected rows."""
        query = f"DELETE FROM {table} WHERE {where}"
        cursor = self.conn.execute(query, tuple(where_params))
        self.commit()

        return cursor.rowcount

    def commit(self) -> None:
        """Commit current transaction."""
        self.conn.commit()

    def rollback(self) -> None:
        """Rollback current transaction."""
        self.conn.rollback()

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            try:
                self._conn.close()
            finally:
                self._conn = None

    def executescript(self, script: str) -> None:
        """Execute multiple SQL statements."""
        self.conn.executescript(script)
        self.commit()