"""
log_controller.py

Steuert das Filtern und Abrufen von Logs für die GUI.
"""

from core.logging.logic import logger
from core.logging.models.log_entry import LogEntry

class LogController:
    def __init__(self):
        self.filter_user_id = None
        self.filter_username = None
        self.filter_feature = None
        self.filter_level = None
        self.filter_start_date = None
        self.filter_end_date = None
        self.limit = 1000

    def get_filter_options(self):
        logs = self.get_logs(limit=10000)
        users = sorted({log.username for log in logs if log.username})
        features = sorted({log.feature for log in logs})
        levels = sorted({log.log_level for log in logs})
        return {"users": users, "features": features, "levels": levels}

    def get_logs(self, limit=None):
        if limit is None:
            limit = self.limit
        logs = logger.query_logs(
            user_id=self.filter_user_id,
            username=self.filter_username,
            feature=self.filter_feature,
            level=self.filter_level,
            # Filter für start_date und end_date können noch eingebaut werden!
            limit=limit,
        )
        return logs

    def clear_all_logs(self):
        logger.clear_logs()

    def printLogs(self):
        logs = self.get_logs()
        print("Aktuelle Logs:")
        for log in logs:
            print(f"{log.timestamp} | {log.log_level} | {log.username} | {log.feature} | {log.event}")
