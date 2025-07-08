"""log_controller.py

Controller for the logging subsystem: filtering, sorting, archiving …

This module contains no GUI code.  All methods are safe to call from
multiple UI components or background tasks.

© QMToolPyV4 – 2025
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import datetime, date, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

# Singleton logger instance
from core.logging.logic.logger import logger
from core.logging.logic import log_export_utils
from core.logging.models.log_entry import LogEntry


class LogController:
    """Encapsulates **all** business logic around application logging."""

    # ---------------------------------------------------------------------#
    # Construction                                                         #
    # ---------------------------------------------------------------------#

    def __init__(self) -> None:
        # filter state – is overwritten on every get_logs(..) call
        self.filter_user_id: Optional[int] = None
        self.filter_username: Optional[str] = None
        self.filter_feature: Optional[str] = None
        self.filter_event: Optional[str] = None            # NEW
        self.filter_reference_id: Optional[str] = None     # NEW
        self.filter_level: Optional[str] = None
        self.filter_start_date: Optional[date] = None
        self.filter_end_date: Optional[date] = None

        # generic settings
        self.limit: int = 1_000
        self._sort_column: str = "timestamp"
        self._sort_ascending: bool = False

    # ---------------------------------------------------------------------#
    # Public API – used by LogView & other clients                          #
    # ---------------------------------------------------------------------#

    def get_filter_options(self) -> Dict[str, List[str]]:
        """Return unique values for combo-box population (features, events, levels)."""
        logs = self.get_logs(limit=10_000)
        return {
            "features": sorted({l.feature for l in logs if l.feature}),
            "events":   sorted({l.event for l in logs if l.event}),
            "levels":   sorted({l.log_level for l in logs if l.log_level}),
        }

    def set_sorting(self, column: str, ascending: bool) -> None:
        """Persist current sort order so every following call uses it."""
        self._sort_column = column
        self._sort_ascending = ascending

    # ------------------------------------------------------------------ #
    # Main entry point                                                   #
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
    ) -> List[LogEntry]:
        """
        Fetch log entries according to the supplied filter arguments.

        Every keyword argument is optional.  Passing ``None`` explicitly
        **clears** the corresponding internal filter, while omitting an
        argument leaves the previous value untouched.  This behaviour
        allows one-liners like ``controller.get_logs(feature="Import")``
        as well as the full filter update done by LogView.
        """
        # ------------------------------------------------------------------
        # 1) Remember / clear filter state
        # ------------------------------------------------------------------
        self.filter_user_id = user_id
        self.filter_username = username
        self.filter_feature = feature
        self.filter_event = event
        self.filter_reference_id = reference_id
        self.filter_level = log_level
        self.filter_start_date = start_date
        self.filter_end_date = end_date

        # ------------------------------------------------------------------
        # 2) Compose query for the logger
        #    Only convert dates once – logger works with ISO timestamps
        # ------------------------------------------------------------------
        if limit is None:
            limit = self.limit

        raw = logger.query_logs(
            user_id=self.filter_user_id,
            username=self.filter_username,
            feature=self.filter_feature,
            event=self.filter_event,                 # NEW
            reference_id=self.filter_reference_id,   # NEW
            level=self.filter_level,
            start_time=self._date_to_iso(self.filter_start_date, True)
            if self.filter_start_date
            else None,
            end_time=self._date_to_iso(self.filter_end_date, False)
            if self.filter_end_date
            else None,
            limit=limit,
        )

        # ------------------------------------------------------------------
        # 3) Sorting
        # ------------------------------------------------------------------
        key_fn = (
            lambda l: getattr(l, self._sort_column)
            if self._sort_column != "timestamp"
            else l.timestamp
        )
        return sorted(raw, key=key_fn, reverse=not self._sort_ascending)

    # ------------------------------------------------------------------ #
    # Archive / Delete helpers                                           #
    # ------------------------------------------------------------------ #

    def archive_logs(self, older_than: date, file_path: str | Path) -> int:
        """Export & delete all logs older than *older_than*."""
        candidates = self._query_older_than(older_than)
        if not candidates:
            return 0
        log_export_utils.export_logs_to_json(candidates, str(file_path))
        self._delete_logs_in_db({c.id for c in candidates})
        return len(candidates)

    def delete_logs(self, older_than: date) -> int:
        """Delete logs older than *older_than* without exporting first."""
        candidates = self._query_older_than(older_than)
        self._delete_logs_in_db({c.id for c in candidates})
        return len(candidates)

    # ------------------------------------------------------------------ #
    # Export / Print                                                     #
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

    # ------------------------------------------------------------------ #
    # Internals                                                          #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _date_to_iso(d: date | None, start_of_day: bool) -> str:
        """Convert a *date* into an ISO-8601 timestamp (UTC)."""
        if d is None:
            # Should never be called this way, but keeps mypy happy.
            return ""
        if start_of_day:
            dt = datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc)
        else:
            dt = datetime.combine(d, datetime.max.time(), tzinfo=timezone.utc)
        return dt.isoformat()

    # -- helpers for archive/delete -------------------------------------#

    def _query_older_than(self, older_than: date) -> List[LogEntry]:
        end_ts = self._date_to_iso(older_than, True)
        return logger.query_logs(end_time=end_ts, limit=10_000_000)

    @staticmethod
    def _delete_logs_in_db(ids: set[int | None]) -> None:
        ids_no_none = {i for i in ids if i is not None}
        if not ids_no_none:
            return
        placeholders = ",".join("?" * len(ids_no_none))
        sql = f"DELETE FROM logs WHERE id IN ({placeholders})"
        with sqlite3.connect(str(logger.db_path)) as conn:
            conn.cursor().execute(sql, tuple(ids_no_none))
            conn.commit()
