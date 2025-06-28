"""
logger.py

Singleton Logger-Modul für das Logging-System.
Verwaltet Logeinträge und persistiert sie in SQLite.
"""

import threading
from pathlib import Path
import os
import sqlite3

from core.logging.models.log_entry import LogEntry

DB_PATH = Path(os.getcwd()) / "databases" / "logging.db"

class Logger:
    """
    Singleton-Logger für das Logging-System.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._lock = threading.Lock()
        self.db_path = DB_PATH
        self.entries = []
        self._ensure_db()

    def _ensure_db(self):
        os.makedirs(self.db_path.parent, exist_ok=True)
        with sqlite3.connect(str(self.db_path)) as conn:
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    user_id INTEGER,
                    username TEXT,
                    feature TEXT NOT NULL,
                    event TEXT NOT NULL,
                    reference_id TEXT,
                    message TEXT,
                    log_level TEXT NOT NULL DEFAULT 'INFO'
                )
            """)
            conn.commit()

    def log(self, feature: str, event: str, user_id: int = None, username: str = None,
            level: str = "INFO", reference_id: str = None, message: str = None):
        """
        Fügt einen Logeintrag hinzu.
        """
        from datetime import datetime, timezone
        timestamp = datetime.now(timezone.utc).isoformat()
        entry = LogEntry(
            id=None,
            timestamp=timestamp,
            user_id=user_id,
            username=username,
            feature=feature,
            event=event,
            reference_id=reference_id,
            message=message,
            log_level=level,
        )
        self.entries.append(entry)
        self._insert_log(entry)

    def _insert_log(self, entry: LogEntry):
        with sqlite3.connect(str(self.db_path)) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO logs (timestamp, user_id, username, feature, event, reference_id, message, log_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.timestamp,
                entry.user_id,
                entry.username,
                entry.feature,
                entry.event,
                entry.reference_id,
                entry.message,
                entry.log_level,
            ))
            conn.commit()

    def fetch_logs(self, limit=100):
        """
        Holt die letzten Logeinträge aus der DB.
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            c = conn.cursor()
            c.execute(
                "SELECT * FROM logs ORDER BY timestamp DESC LIMIT ?", (limit,)
            )
            rows = c.fetchall()
            return [LogEntry.from_dict(dict(zip([column[0] for column in c.description], row))) for row in rows]

    def query_logs(self, user_id=None, username=None, feature=None, level=None,
                   start_time=None, end_time=None, limit=1000):
        """
        Flexible Abfrage der Logs mit Filtern.
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            c = conn.cursor()
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
            c.execute(query, params)
            rows = c.fetchall()
            return [LogEntry.from_dict(dict(zip([column[0] for column in c.description], row))) for row in rows]

    def clear_logs(self):
        """
        Löscht alle Logs.
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM logs")
            conn.commit()

# Globale Logger-Singleton-Instanz
logger = Logger()
