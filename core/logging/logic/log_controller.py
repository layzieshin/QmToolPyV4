"""
log_controller.py

Erweiterte Version mit Null-sicherer Sortierung.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import datetime, date, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

from core.logging.logic.logger import logger
from core.logging.logic import log_export_utils
from core.logging.models.log_entry import LogEntry


class LogController:
    """High-level Business-Logic für Logs."""

    def __init__(self) -> None:
        # Filter-State
        self.filter_user_id: Optional[int] = None
        self.filter_username: Optional[str] = None
        self.filter_feature: Optional[str] = None
        self.filter_event: Optional[str] = None
        self.filter_reference_id: Optional[str] = None
        self.filter_level: Optional[str] = None
        self.filter_start_date: Optional[date] = None
        self.filter_end_date: Optional[date] = None

        # Sortier-State
        self.limit = 1_000
        self._sort_column = "timestamp"
        self._sort_ascending = False

    # ------------------------------------------------------------------ #
    # Öffentliche API                                                    #
    # ------------------------------------------------------------------ #
    def set_sorting(self, column: str, ascending: bool) -> None:
        self._sort_column = column
        self._sort_ascending = ascending

    def get_filter_options(self) -> Dict[str, List[str]]:
        """
        Get unique filter options directly from the database using SQL DISTINCT.
        This is much more efficient than loading all logs into memory.
        """
        with sqlite3.connect(str(logger.db_path)) as conn:
            features = [r[0] for r in conn.execute(
                "SELECT DISTINCT feature FROM logs WHERE feature IS NOT NULL ORDER BY feature"
            ).fetchall()]
            events = [r[0] for r in conn.execute(
                "SELECT DISTINCT event FROM logs WHERE event IS NOT NULL ORDER BY event"
            ).fetchall()]
            levels = [r[0] for r in conn.execute(
                "SELECT DISTINCT log_level FROM logs WHERE log_level IS NOT NULL ORDER BY log_level"
            ).fetchall()]
        return {
            "features": features,
            "events": events,
            "levels": levels,
        }

    # ------------------------------------------------------------------ #
    # Hauptmethode                                                       #
    # ------------------------------------------------------------------ #
    def get_logs(
        self,
        *,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        feature: Optional[str] = None,
        event: Optional[str] = None,
        reference_id: Optional[str] = None,
        log_level: Optional[str] = None,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        # --- Filterwerte merken ----------------------------------------
        self.filter_user_id = user_id
        self.filter_username = username
        self.filter_feature = feature
        self.filter_event = event
        self.filter_reference_id = reference_id
        self.filter_level = log_level
        self.filter_start_date = start_date
        self.filter_end_date = end_date

        if limit is None:
            limit = self.limit

        raw: List[LogEntry] = logger.query_logs(
            user_id=user_id,
            username=username,
            feature=feature,
            event=event,
            reference_id=reference_id,
            level=log_level,
            start_time=self._date_to_iso(start_date, True) if start_date else None,
            end_time=self._date_to_iso(end_date, False) if end_date else None,
            limit=limit,
        )

        # --- Null-sichere Sortierung -----------------------------------
        def _safe_key(entry: LogEntry):
            if self._sort_column == "timestamp":
                return entry.timestamp or datetime.min
            val = getattr(entry, self._sort_column, "")
            return val if val is not None else ""

        raw_sorted = sorted(raw, key=_safe_key, reverse=not self._sort_ascending)

        # --- Dicts für GUI ---------------------------------------------
        return [e.as_dict() for e in raw_sorted]

    # ------------------------------------------------------------------ #
    # Archiv / Delete (unverändert)                                      #
    # ------------------------------------------------------------------ #
    def archive_logs(self, older_than: date, file_path: str | Path) -> int:
        candidates = self._query_older_than(older_than)
        if not candidates:
            return 0
        log_export_utils.export_logs_to_json([c.as_dict() for c in candidates],
                                             str(file_path))
        self._delete_logs_in_db({c.id for c in candidates})
        return len(candidates)

    def delete_logs(self, older_than: date) -> int:
        candidates = self._query_older_than(older_than)
        self._delete_logs_in_db({c.id for c in candidates})
        return len(candidates)

    # ------------------------------------------------------------------ #
    # Hilfsfunktionen                                                    #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _date_to_iso(d: date | None, start_of_day: bool) -> str:
        if d is None:
            return ""
        t = datetime.min.time() if start_of_day else datetime.max.time()
        return datetime.combine(d, t, tzinfo=timezone.utc).isoformat()

    def _query_older_than(self, older_than: date) -> List[LogEntry]:
        end_ts = self._date_to_iso(older_than, True)
        return logger.query_logs(end_time=end_ts, limit=10_000_000)

    @staticmethod
    def _delete_logs_in_db(ids: set[int | None]) -> None:
        real_ids = {i for i in ids if i is not None}
        if not real_ids:
            return
        q = ",".join("?" * len(real_ids))
        with sqlite3.connect(str(logger.db_path)) as conn:
            conn.execute(f"DELETE FROM logs WHERE id IN ({q})", tuple(real_ids))
            conn.commit()
    # ------------------------------------------------------------------ #
    # Export / Print  (optional)                                         #
    # ------------------------------------------------------------------ #
    @staticmethod
    def export_logs_to_json(logs: List[Dict[str, Any]], file_path: str | Path) -> None:
        with open(file_path, "w", encoding="utf-8") as fh:
            json.dump(logs, fh, indent=4, ensure_ascii=False)

    @staticmethod
    def print_logs(logs: List[Dict[str, Any]]) -> None:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json", encoding="utf-8"
        )
        json.dump(logs, tmp, indent=4, ensure_ascii=False)
        tmp.close()
        log_export_utils.print_file(tmp.name)
