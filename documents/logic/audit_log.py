from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from sqlite3 import Connection


class AuditLog:
    def __init__(self, conn: Connection) -> None:
        self._c = conn
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._c.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id TEXT NOT NULL,
                ts_utc TEXT NOT NULL,
                user_id TEXT,
                action TEXT NOT NULL,
                details TEXT
            )
        """)

    def write(self, doc_id: str, action: str, user_id: str | None, details: dict[str, Any] | None = None) -> None:
        self._c.execute(
            "INSERT INTO audit_log(doc_id, ts_utc, user_id, action, details) VALUES (?,?,?,?,?)",
            (doc_id, datetime.utcnow().isoformat(timespec="seconds"), user_id, action,
             json.dumps(details or {}, ensure_ascii=False))
        )
