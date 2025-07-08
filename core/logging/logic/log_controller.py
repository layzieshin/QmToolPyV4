"""log_controller.py

Controller für das Log-Subsystem: Filter, Sortierung, Archivierung …
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import datetime, date, timezone
from pathlib import Path
from typing import List, Dict, Any

# **NEU** ­– wir importieren jetzt die Instanz, nicht das Modul
from core.logging.logic.logger import logger          # <- Singleton-Instanz
from core.logging.logic import log_export_utils
from core.logging.models.log_entry import LogEntry


class LogController:
    """Kapselt alle nicht-UI-Aufgaben rund ums Logging."""

    # ------------------------------------------------------------------ #
    # Construction                                                       #
    # ------------------------------------------------------------------ #

    def __init__(self) -> None:
        self.filter_user_id: int | None = None
        self.filter_username: str | None = None
        self.filter_feature: str | None = None
        self.filter_level: str | None = None
        self.filter_start_date: date | None = None
        self.filter_end_date: date | None = None
        self.limit: int = 1_000

        self._sort_column: str = "timestamp"
        self._sort_ascending: bool = False

    # ------------------------------------------------------------------ #
    # Öffentliche API für LogView                                        #
    # ------------------------------------------------------------------ #

    def get_filter_options(self) -> Dict[str, List[str]]:
        logs = self.get_logs(limit=10_000)
        return {
            "features": sorted({l.feature for l in logs}),
            "events":   sorted({l.event for l in logs}),
            "levels":   sorted({l.log_level for l in logs}),
        }

    def set_sorting(self, column: str, ascending: bool) -> None:
        self._sort_column = column
        self._sort_ascending = ascending

    def get_logs(self, limit: int | None = None) -> List[LogEntry]:
        if limit is None:
            limit = self.limit

        raw = logger.query_logs(                   # <-- funktioniert jetzt
            user_id=self.filter_user_id,
            username=self.filter_username,
            feature=self.filter_feature,
            level=self.filter_level,
            start_time=self._date_to_iso(self.filter_start_date, True)
            if self.filter_start_date else None,
            end_time=self._date_to_iso(self.filter_end_date, False)
            if self.filter_end_date else None,
            limit=limit,
        )

        key_fn = (
            (lambda l: getattr(l, self._sort_column))
            if self._sort_column != "timestamp"
            else (lambda l: l.timestamp)
        )
        return sorted(raw, key=key_fn, reverse=not self._sort_ascending)

    # ------------------------------------------------------------------ #
    # Archivieren / Löschen                                              #
    # ------------------------------------------------------------------ #

    def archive_logs(self, older_than: date, file_path: str | Path) -> int:
        candidates = self._query_older_than(older_than)
        if not candidates:
            return 0
        log_export_utils.export_logs_to_json(candidates, str(file_path))
        self._delete_logs_in_db({c.id for c in candidates})
        return len(candidates)

    def delete_logs(self, older_than: date) -> int:
        candidates = self._query_older_than(older_than)
        self._delete_logs_in_db({c.id for c in candidates})
        return len(candidates)

    # ------------------------------------------------------------------ #
    # Export / Print                                                     #
    # ------------------------------------------------------------------ #

    def export_logs_to_json(self, logs: List[Dict[str, Any]], file_path: str | Path) -> None:
        with open(file_path, "w", encoding="utf-8") as fh:
            json.dump(logs, fh, indent=4, ensure_ascii=False)

    def print_logs(self, logs: List[Dict[str, Any]]) -> None:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json", encoding="utf-8"
        )
        json.dump(logs, tmp, indent=4, ensure_ascii=False)
        tmp.close()
        log_export_utils.print_file(tmp.name)

    # ------------------------------------------------------------------ #
    # Interne Helfer                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _date_to_iso(d: date, start_of_day: bool) -> str:
        if start_of_day:
            dt = datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc)
        else:
            dt = datetime.combine(d, datetime.max.time(), tzinfo=timezone.utc)
        return dt.isoformat()

    def _query_older_than(self, older_than: date) -> List[LogEntry]:
        end_ts = self._date_to_iso(older_than, True)
        return logger.query_logs(end_time=end_ts, limit=10_000_000)

    def _delete_logs_in_db(self, ids: set[int | None]) -> None:
        ids_no_none = {i for i in ids if i is not None}
        if not ids_no_none:
            return
        placeholders = ",".join("?" * len(ids_no_none))
        sql = f"DELETE FROM logs WHERE id IN ({placeholders})"
        # **FIX** – Zugriff direkt auf logger.db_path
        with sqlite3.connect(str(logger.db_path)) as conn:
            conn.cursor().execute(sql, tuple(ids_no_none))
            conn.commit()
