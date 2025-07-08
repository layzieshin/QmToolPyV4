"""
logger.py

Thread-safe Singleton-Logger.

Persistiert Logeinträge in einer SQLite-Datenbank und bietet flexible
Abfrage-Methoden mit Filter- und Limit-Unterstützung.

© QMToolPyV4 – 2025
"""

from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from core.logging.models.log_entry import LogEntry

# --------------------------------------------------------------------------- #
# Konstanten & Pfade                                                          #
# --------------------------------------------------------------------------- #

DB_PATH = Path(os.getcwd()) / "databases" / "logging.db"


# --------------------------------------------------------------------------- #
# Singleton-Klasse                                                            #
# --------------------------------------------------------------------------- #

class Logger:
    """
    **Thread-sicherer** Singleton, der alle Log-Operationen kapselt.

    - `log(...)`         – neuen Eintrag hinzufügen
    - `fetch_logs(...)`  – letzte *n* Einträge holen
    - `query_logs(...)`  – flexible Filter-Abfrage (GUI & LogController)
    """

    _instance: "Logger | None" = None
    _instance_lock = threading.Lock()

    # --------------------------------------------------------------------- #
    # Construction                                                          #
    # --------------------------------------------------------------------- #

    def __new__(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False   # type: ignore[attr-defined]
        return cls._instance  # type: ignore[return-value]

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            # Bereits initialisiert – Singleton-Verhalten.
            return

        # Initialisierung (wird genau einmal ausgeführt)
        self._initialized = True
        self._lock = threading.Lock()
        self.db_path: Path = DB_PATH
        self.entries: list[LogEntry] = []
        self._ensure_db()

    # --------------------------------------------------------------------- #
    # Öffentliche API                                                        #
    # --------------------------------------------------------------------- #

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
        Füge einen neuen Logeintrag hinzu und persistiere ihn sofort.

        Alle Parameter außer *feature* und *event* sind optional.
        """
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

        # In-Memory-Liste nur als Cache für Kleinstanfragen
        self.entries.append(entry)
        self._insert_log(entry)

    def fetch_logs(self, limit: int = 100) -> List[LogEntry]:
        """
        Hole die *zuletzt* geschriebenen Logeinträge (DESCending sortiert).
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            c = conn.cursor()
            c.execute(
                "SELECT * FROM logs ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
            rows = c.fetchall()
            return [
                LogEntry.from_dict(dict(zip([col[0] for col in c.description], row)))
                for row in rows
            ]

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
        """
        Flexibel Logs filtern.

        **Keyword-only-Parameter** (Absicht: bessere Lesbarkeit):

        - ``user_id`` / ``username`` – Benutzerfilter
        - ``feature`` – Feature-Name (z. B. ``"Import"``)
        - ``event`` – Feineres Event innerhalb eines Features
        - ``reference_id`` – Freies Textfeld für Geschäftsobjekt-IDs
        - ``level`` – Log-Level (``"INFO"``, ``"WARNING"`` …)
        - ``start_time`` – ISO-8601 Timestamp *>=*
        - ``end_time`` – ISO-8601 Timestamp *<=*
        - ``limit`` – maximale Rückgabeanzahl (Default = 1000)
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            c = conn.cursor()

            query = "SELECT * FROM logs WHERE 1=1"
            params: list[object] = []

            # Dynamisch WHERE-Klausel erweitern
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

            return [
                LogEntry.from_dict(dict(zip([col[0] for col in c.description], row)))
                for row in rows
            ]

    def clear_logs(self) -> None:
        """
        **Entwickler-Hilfsmethode:** Löscht *alle* Einträge (irreversibel).
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.cursor().execute("DELETE FROM logs")
            conn.commit()

    # --------------------------------------------------------------------- #
    # Interne Helfer                                                        #
    # --------------------------------------------------------------------- #

    def _ensure_db(self) -> None:
        """
        Erstellt die SQLite-Tabelle, falls sie noch nicht existiert.
        """
        os.makedirs(self.db_path.parent, exist_ok=True)
        with sqlite3.connect(str(self.db_path)) as conn:
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
        """
        Persistiert einen einzelnen Logeintrag atomar.
        """
        with sqlite3.connect(str(self.db_path)) as conn:
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
# Globale Singleton-Instanz (Import-freundlich)                               #
# --------------------------------------------------------------------------- #

logger = Logger()
