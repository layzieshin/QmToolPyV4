"""
log_controller.py

Controller class for the logging feature of QMToolPyV2.

Handles filtering, sorting, fetching logs,
as well as archiving, deleting, exporting, and printing.

All date and time conversions are delegated to
core/utils/date_time_helpers for clean separation of concerns.
"""

from datetime import datetime, date
from typing import List, Dict, Optional

from core.logging.logic.logger import logger
from core.utils.date_time_helpers import local_date_to_utc_range, utc_to_local_str
from core.logging.logic.log_export_utils import export_logs_to_json, print_logs

class LogController:
    """
    Controller managing interaction between UI and Logger logic.

    Provides methods to fetch logs with various filters,
    format timestamps for display, and perform actions
    such as archiving, deletion, export, and printing.
    """

    def __init__(self):
        self.sort_column = "timestamp"
        self.sort_ascending = False

    def get_filter_options(self) -> Dict[str, List[str]]:
        """
        Retrieves unique values for feature, event, and log level filters.
        """
        logs = self.get_logs(limit=10000)
        features = sorted(set(log["feature"] for log in logs if log["feature"]))
        events = sorted(set(log["event"] for log in logs if log["event"]))
        levels = sorted(set(log["log_level"] for log in logs if log["log_level"]))
        return {"features": features, "events": events, "levels": levels}

    def set_sorting(self, column: str, ascending: bool):
        """
        Set current sort column and direction (called by LogView).
        """
        self.sort_column = column
        self.sort_ascending = ascending

    def get_logs(self,
                 start_date: Optional[date] = None,
                 end_date: Optional[date] = None,
                 feature: Optional[str] = None,
                 event: Optional[str] = None,
                 reference_id: Optional[str] = None,
                 log_level: Optional[str] = None,
                 limit: int = 1000) -> List[Dict]:
        """
        Fetches logs filtered by local start/end dates plus additional criteria.
        Converts local dates to UTC time ranges for querying the database.
        """
        filters = []
        if start_date and end_date:
            start_utc, end_utc = local_date_to_utc_range(start_date, end_date)
            filters.append(("timestamp", ">=", start_utc))
            filters.append(("timestamp", "<=", end_utc))
        if feature:
            filters.append(("feature", "=", feature))
        if event:
            filters.append(("event", "=", event))
        if reference_id:
            filters.append(("reference_id", "=", reference_id))
        if log_level:
            filters.append(("log_level", "=", log_level))
        # You can add more filters as needed

        return logger.repository.query_logs(
            filters=filters,
            limit=limit,
            order_by=self.sort_column,
            ascending=self.sort_ascending,
        )

    def format_timestamp(self, utc_iso: str) -> str:
        """
        Formats a UTC ISO8601 timestamp string into a local date-time string.
        """
        return utc_to_local_str(utc_iso)

    def archive_logs(self, older_than: date, path: str) -> int:
        """
        Archives logs older than the specified local date by exporting them to JSON and deleting them.

        :param older_than: Local date threshold; logs older than this will be archived
        :param path: File path to save the JSON archive
        :return: Number of logs archived
        """
        # Get UTC timestamp for threshold date
        start_utc, end_utc = local_date_to_utc_range(date.min, older_than)
        logs = logger.repository.query_logs(
            filters=[
                ("timestamp", "<", end_utc)
            ]
        )
        if logs:
            export_logs_to_json(logs, path)
            deleted = logger.repository.delete_logs_older_than(end_utc)
            return deleted
        return 0

    def delete_logs(self, older_than: date) -> int:
        """
        Deletes logs older than the specified local date.

        :param older_than: Local date threshold; logs older than this will be deleted
        :return: Number of logs deleted
        """
        _, end_utc = local_date_to_utc_range(date.min, older_than)
        return logger.repository.delete_logs_older_than(end_utc)

    def export_logs_to_json(self, logs: List[Dict], path: str):
        """
        Exports a list of log entries to a JSON file.

        :param logs: List of log dictionaries
        :param path: Destination file path for the JSON export
        """
        export_logs_to_json(logs, path)

    def print_logs(self, logs: List[Dict]):
        """
        Prints the given log entries in a formatted text format.

        :param logs: List of log dictionaries
        """
        print_logs(logs, self.format_timestamp)
