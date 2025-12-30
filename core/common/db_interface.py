"""
core/common/db_interface.py
===========================

Shared interface + helpers for SQLite-backed modules.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
import sqlite3


def create_sqlite_connection(
    db_path: Path,
    *,
    check_same_thread: bool = False,
    foreign_keys: bool = False,
) -> sqlite3.Connection:
    """Create a sqlite3 connection with common defaults."""
    conn = sqlite3.connect(str(db_path), check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    if foreign_keys:
        conn.execute("PRAGMA foreign_keys = ON")
    return conn


class DatabaseAccess(ABC):
    """Interface for modules that depend on a database."""

    @property
    @abstractmethod
    def db_path(self) -> Path:
        raise NotImplementedError

    @abstractmethod
    def connect(self) -> sqlite3.Connection:
        raise NotImplementedError


class SQLiteRepository(DatabaseAccess):
    """Default SQLite implementation with optional shared connection."""

    def __init__(
        self,
        db_path: Path,
        *,
        check_same_thread: bool = False,
        foreign_keys: bool = False,
    ) -> None:
        self._db_path = Path(db_path)
        self._conn: Optional[sqlite3.Connection] = None
        self._check_same_thread = check_same_thread
        self._foreign_keys = foreign_keys

    @property
    def db_path(self) -> Path:
        return self._db_path

    @property
    def conn(self) -> sqlite3.Connection:
        return self.connect()

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = create_sqlite_connection(
                self._db_path,
                check_same_thread=self._check_same_thread,
                foreign_keys=self._foreign_keys,
            )
        return self._conn

    def new_connection(self) -> sqlite3.Connection:
        return create_sqlite_connection(
            self._db_path,
            check_same_thread=self._check_same_thread,
            foreign_keys=self._foreign_keys,
        )

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None
