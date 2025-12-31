# core/common/db_api.py
from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from core.config.config_loader import config_loader
from core.common.db_interface import create_sqlite_connection  # reuse helper

dbpath = config_loader.get_database_path()

class DatabaseAPI:
    """
    Thin central database API for sqlite-backed storages.
    Provides:
    - connect() context manager
    - simple CRUD helpers (insert, update, delete, get_by_id, query)
    - transaction() contextmanager
    """

    def __init__(self, dbpath: Path, *, foreign_keys: bool = True, check_same_thread: bool = False):
        self.db_path = dbpath
        self._foreign_keys = foreign_keys
        self._check_same_thread = check_same_thread

    def connect(self) -> sqlite3.Connection:
        """Return a sqlite3.Connection configured with defaults."""
        return create_sqlite_connection(dbpath, check_same_thread=self._check_same_thread, foreign_keys=self._foreign_keys)

    @contextmanager
    def transaction(self):
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute(self, sql: str, params: Iterable[Any] = (), commit: bool = False) -> sqlite3.Cursor:
        with self.connect() as conn:
            cur = conn.execute(sql, tuple(params))
            if commit:
                conn.commit()
            rows = cur  # cursor returned
            return rows

    def fetchone(self, sql: str, params: Iterable[Any] = ()):
        with self.connect() as conn:
            cur = conn.execute(sql, tuple(params))
            return cur.fetchone()

    def fetchall(self, sql: str, params: Iterable[Any] = ()):
        with self.connect() as conn:
            cur = conn.execute(sql, tuple(params))
            return cur.fetchall()

    def insert(self, table: str, data: Dict[str, Any]) -> int:
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        values = tuple(data.values())
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        with self.transaction() as conn:
            cur = conn.execute(sql, values)
            return cur.lastrowid

    def update(self, table: str, data: Dict[str, Any], where: str, where_params: Iterable[Any] = ()):
        set_frag = ", ".join([f"{k}=?" for k in data.keys()])
        params = tuple(data.values()) + tuple(where_params)
        sql = f"UPDATE {table} SET {set_frag} WHERE {where}"
        with self.transaction() as conn:
            cur = conn.execute(sql, params)
            return cur.rowcount

    def delete(self, table: str, where: str, where_params: Iterable[Any] = ()):
        sql = f"DELETE FROM {table} WHERE {where}"
        with self.transaction() as conn:
            cur = conn.execute(sql, tuple(where_params))
            return cur.rowcount

    def get_by_id(self, table: str, id_col: str, id_value: Any):
        sql = f"SELECT * FROM {table} WHERE {id_col} = ?"
        return self.fetchone(sql, (id_value,))