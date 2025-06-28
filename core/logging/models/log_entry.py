"""
log_entry.py

Definiert das LogEntry-Datenmodell für das Logging-System.
"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class LogEntry:
    """
    Datenklasse für einen Logeintrag.
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
        Erzeugt ein LogEntry-Objekt aus einem Dictionary.
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
        Wandelt das LogEntry-Objekt in ein Dictionary um.
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
