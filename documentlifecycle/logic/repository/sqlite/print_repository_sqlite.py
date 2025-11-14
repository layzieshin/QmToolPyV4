"""
===============================================================================
DocumentPrintRepositorySQLite – per-user print counters
-------------------------------------------------------------------------------
Schema
    document_prints(document_id INTEGER, user_id INTEGER NULL,
                    count INTEGER NOT NULL DEFAULT 0,
                    last_printed_at TEXT,
                    PRIMARY KEY(document_id, user_id))

Use
    increment_count(document_id, user_id) -> None
    get_total(document_id) -> int
===============================================================================
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional
import sqlite3

from .base_sqlite_repo import BaseSQLiteRepo


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS document_prints (
            document_id INTEGER NOT NULL,
            user_id INTEGER,
            count INTEGER NOT NULL DEFAULT 0,
            last_printed_at TEXT,
            PRIMARY KEY(document_id, user_id)
        );
        """
    )
    conn.commit()


class DocumentPrintRepositorySQLite(BaseSQLiteRepo):
    def __init__(self) -> None:
        super().__init__(None)
        _ensure_schema(self.conn)

    def increment_count(self, *, document_id: int, user_id: Optional[int]) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        cur = self.conn.execute(
            "SELECT count FROM document_prints WHERE document_id=? AND user_id IS ?",
            (document_id, user_id),
        )
        row = cur.fetchone()
        if row:
            self.conn.execute(
                "UPDATE document_prints SET count = count + 1, last_printed_at=? WHERE document_id=? AND user_id IS ?",
                (now, document_id, user_id),
            )
        else:
            self.conn.execute(
                "INSERT INTO document_prints(document_id, user_id, count, last_printed_at) VALUES (?,?,?,?)",
                (document_id, user_id, 1, now),
            )
        self.conn.commit()

    def get_total(self, *, document_id: int) -> int:
        cur = self.conn.execute(
            "SELECT SUM(count) FROM document_prints WHERE document_id=?",
            (document_id,),
        )
        val = cur.fetchone()
        return int(val[0] or 0)
