"""
core/logging/logic/logger.py
============================

Thread-sicherer Singleton-Logger mit SQLite-Backend und
Auto-Fill des Benutzernamens, falls nicht explizit angegeben.

Performance optimizations:
- Reuses a single database connection instead of creating new ones per operation
- Connection is thread-safe via check_same_thread=False and explicit locking
"""

from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from core.config.config_loader import config_loader
from core.logging.models.log_entry import LogEntry

# --------------------------------------------------------------------------- #
#  Pfad zur Logging-Datenbank                                                 #
# --------------------------------------------------------------------------- #
LOG_DB_PATH: Path = config_loader.get_logging_db_path()


# --------------------------------------------------------------------------- #
#  Singleton-Klasse                                                           #
# --------------------------------------------------------------------------- #
class Logger:
    """Thread-sicherer Singleton-Logger mit Auto-Username."""

    _instance: "Logger | None" = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "Logger":  # noqa: D401
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False  # type: ignore[attr-defined]
        return cls._instance  # type: ignore[return-value]

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        self._lock = threading.Lock()
        self.db_path: Path = LOG_DB_PATH
        self.entries: list[LogEntry] = []
        self._conn: sqlite3.Connection | None = None
        self._ensure_db()

    # ------------------------------------------------------------------ #
    #  Connection management (reuse single connection)                   #
    # ------------------------------------------------------------------ #
    def _get_connection(self) -> sqlite3.Connection:
        """Get or create a reusable database connection (thread-safe)."""
        if self._conn is None:
            with self._lock:
                # Double-check pattern for thread safety
                if self._conn is None:
                    os.makedirs(self.db_path.parent, exist_ok=True)
                    self._conn = sqlite3.connect(
                        str(self.db_path),
                        check_same_thread=False,  # Allow multi-threaded access
                    )
                    self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self) -> None:
        """Close the database connection and release resources."""
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None

    # ------------------------------------------------------------------ #
    #  Öffentliche API: log                                              #
    # ------------------------------------------------------------------ #
    def log(
        self,
        feature: str,
        event: str,
        *,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        level: str = "INFO",
        reference_id: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        """
        Persistiert einen Logeintrag.

        Auto-Username: Wird *username* weggelassen, versucht der Logger
        `AppContext.current_user.username` zu verwenden. Gelingt das nicht,
        wird "unknown" gespeichert.
        """
        if username is None:
            try:
                # Lazy Import, um Zirkularität zu vermeiden
                from core.common.app_context import AppContext  # noqa: WPS433
                if AppContext.current_user:
                    username = AppContext.current_user.username
            except Exception:  # pragma: no cover
                pass

        timestamp = datetime.now(timezone.utc).isoformat()
        entry = LogEntry(
            id=None,
            timestamp=timestamp,
            user_id=user_id,
            username=username or "unknown",
            feature=feature,
            event=event,
            reference_id=reference_id,
            message=message,
            log_level=level,
        )

        self.entries.append(entry)
        self._insert_log(entry)

    # ------------------------------------------------------------------ #
    #  Fetch / Query / Clear                                             #
    # ------------------------------------------------------------------ #
    def fetch_logs(self, limit: int = 100) -> List[LogEntry]:
        with self._lock:
            conn = self._get_connection()
            c = conn.cursor()
            c.execute(
                "SELECT * FROM logs ORDER BY timestamp DESC LIMIT ?", (limit,)
            )
            rows = c.fetchall()
            return [LogEntry.from_dict(dict(row)) for row in rows]

    def query_logs(
        self,
        *,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        feature: Optional[str] = None,
        event: Optional[str] = None,
        reference_id: Optional[str] = None,
        level: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 1_000,
    ) -> List[LogEntry]:
        with self._lock:
            conn = self._get_connection()
            c = conn.cursor()

            query = "SELECT * FROM logs WHERE 1=1"
            params: list[object] = []

            if user_id is not None:
                query += " AND user_id = ?"
                params.append(user_id)
            if username is not None:
                query += " AND username = ?"
                params.append(username)
            if feature is not None:
                query += " AND feature = ?"
                params.append(feature)
            if event is not None:
                query += " AND event = ?"
                params.append(event)
            if reference_id is not None:
                query += " AND reference_id = ?"
                params.append(reference_id)
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

            return [LogEntry.from_dict(dict(row)) for row in rows]

    def clear_logs(self) -> None:
        with self._lock:
            conn = self._get_connection()
            conn.execute("DELETE FROM logs")
            conn.commit()

    def execute_query(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        """
        Execute a read-only SQL query with thread-safe access.
        
        This method is intended for internal use by LogController and other
        core components with pre-defined, trusted queries. Parameters should
        be passed via the params tuple to prevent SQL injection.
        
        WARNING: Do not pass user-provided strings directly to the query parameter.
        Always use parameterized queries with the params argument.
        
        Args:
            query: SQL query string (should be a constant, not user input)
            params: Query parameters tuple (safe for user input)
            
        Returns:
            List of Row objects
        """
        with self._lock:
            conn = self._get_connection()
            return conn.execute(query, params).fetchall()

    # ------------------------------------------------------------------ #
    #  Interne Helfer                                                    #
    # ------------------------------------------------------------------ #
    def _ensure_db(self) -> None:
        """Initialize the database schema. Thread-safe via lock."""
        with self._lock:
            os.makedirs(self.db_path.parent, exist_ok=True)
            conn = self._get_connection()
            conn.execute(
                """
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
                """
            )
            conn.commit()

    def _insert_log(self, entry: LogEntry) -> None:
        with self._lock:
            conn = self._get_connection()
            conn.execute(
                """
                INSERT INTO logs
                    (timestamp, user_id, username, feature, event,
                     reference_id, message, log_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.timestamp,
                    entry.user_id,
                    entry.username,
                    entry.feature,
                    entry.event,
                    entry.reference_id,
                    entry.message,
                    entry.log_level,
                ),
            )
            conn.commit()


# --------------------------------------------------------------------------- #
#  Globale Instanz                                                            #
# --------------------------------------------------------------------------- #
logger: Logger = Logger()
