"""
logger_repository.py

Verwaltet die SQLite-Datenbank für die persistenten Logeinträge.

- Erstellt die Tabelle, falls noch nicht vorhanden.
- Bietet Methoden zum Einfügen, Abfragen und Löschen von Logs.
"""

import sqlite3
from pathlib import Path
from core.logging.models import Log

class LoggerRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn = None
        self._ensure_db()

    def _connect(self):
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row

    def _ensure_db(self):
        self._connect()
        cursor = self._conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                feature TEXT NOT NULL,
                event TEXT NOT NULL,
                user_id INTEGER,
                username TEXT,
                reference_id TEXT,
                message TEXT,
                log_level TEXT NOT NULL DEFAULT 'INFO'
            )
        """)
        self._conn.commit()

    def insert_log(self, entry: log_entry):
        self._connect()
        cursor = self._conn.cursor()
        cursor.execute(
            """INSERT INTO logs
               (timestamp, feature, event, user_id, username, reference_id, message, log_level)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.timestamp,
                entry.feature,
                entry.event,
                entry.user_id,
                entry.username,
                entry.reference_id,
                entry.message,
                entry.log_level,
            )
        )
        self._conn.commit()

    def fetch_logs(self, limit=100):
        self._connect()
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM logs ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        rows = cursor.fetchall()
        return [log_entry.from_dict(dict(row)) for row in rows]

    def query_logs(self, user_id=None, username=None, feature=None, level=None,
                   start_time=None, end_time=None, limit=1000):
        self._connect()
        cursor = self._conn.cursor()
        query = "SELECT * FROM logs WHERE 1=1"
        params = []

        if user_id is not None:
            query += " AND user_id = ?"
            params.append(user_id)
        if username is not None:
            query += " AND username = ?"
            params.append(username)
        if feature is not None:
            query += " AND feature = ?"
            params.append(feature)
        if level is not None:
            query += " AND log_level = ?"
            params.append(level)
        if start_time is not None:
            query += " AND timestamp >= ?"
            params.append(start_time)
        if end_time is not None:
            query += " AND timestamp <= ?"
            params.append(end_time)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [log_entry.from_dict(dict(row)) for row in rows]

    def clear_logs(self):
        self._connect()
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM logs")
        self._conn.commit()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
