"""
log_entry.py

Defines the LogEntry data model used throughout the logging feature.

Encapsulates all relevant fields of a log entry and provides convenient
methods for conversion between dictionary representations and LogEntry instances.

To be used by Logger, LoggerRepository, LogController, and GUI views.
"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class LogEntry:
    """
    Data class representing a single log entry.

    Fields:
        id: Optional log entry ID (from DB, may be None for new entries)
        timestamp: UTC ISO8601 string of the event
        user_id: Optional user ID associated with the event
        username: Optional user name (string)
        feature: Name of the feature/module generating the log
        event: Event name or short description
        reference_id: Optional reference to related entity (e.g., document ID)
        message: Optional details about the event
        log_level: Severity level ('INFO', 'WARN', 'ERROR', etc.)
    """
    id: Optional[int]
    timestamp: str
    user_id: Optional[int]
    username: Optional[str]
    feature: str
    event: str
    reference_id: Optional[str]
    message: Optional[str]
    log_level: str = "INFO"

    @staticmethod
    def from_dict(data: dict) -> "LogEntry":
        """
        Creates a LogEntry instance from a dictionary.
        """
        return LogEntry(
            id=data.get("id"),
            timestamp=data["timestamp"],
            user_id=data.get("user_id"),
            username=data.get("username"),
            feature=data["feature"],
            event=data["event"],
            reference_id=data.get("reference_id"),
            message=data.get("message"),
            log_level=data.get("log_level", "INFO"),
        )

    def to_dict(self) -> dict:
        """
        Converts the LogEntry instance to a dictionary for serialization/storage.
        """
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "username": self.username,
            "feature": self.feature,
            "event": self.event,
            "reference_id": self.reference_id,
            "message": self.message,
            "log_level": self.log_level,
        }
