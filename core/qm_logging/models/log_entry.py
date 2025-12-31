"""
log_entry.py

Dataclass für einen Logeintrag.

• from_dict()  – baut das Objekt aus einem DB-/JSON-Dict
• as_dict()    – gibt für die GUI ein Dict mit
                 - timestamp_utc (ISO-UTC)
                 - timestamp      (lokale Europe/Berlin-Zeit)
                 zurück.
"""

from __future__ import annotations    # ← muss direkt nach dem Docstring stehen!

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# ------------------------------------------------------------------ #
# Flexibler Import des Helpers                                       #
# ------------------------------------------------------------------ #
try:
    # Hauptpfad in deinem Projekt
    import core.helpers.date_time_helper as dt
except ModuleNotFoundError:           # Fallback z. B. bei Unit-Tests
    import date_time_helper as dt


@dataclass
class LogEntry:
    id: Optional[int]
    timestamp: datetime          # immer UTC
    log_level: str
    user_id: Optional[int]
    username: Optional[str]
    feature: str
    event: str
    reference_id: Optional[str]
    message: Optional[str]

    # -------------------- Factory ------------------------------------ #
    @classmethod
    def from_dict(cls, data: dict) -> "LogEntry":
        """Erzeugt ein LogEntry aus einem DB/JSON-Dict."""
        ts = data["timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        return cls(
            id=data.get("id"),
            timestamp=ts,
            log_level=data.get("log_level", "INFO"),
            user_id=data.get("user_id"),
            username=data.get("username"),
            feature=data.get("feature", ""),
            event=data.get("event", ""),
            reference_id=data.get("reference_id"),
            message=data.get("message"),
        )

    # -------------------- Dict für GUI / Export ---------------------- #
    def as_dict(self) -> dict:
        utc_iso = self.timestamp.replace(microsecond=0).isoformat()
        local_str = dt.utc_to_local_str(utc_iso)  # z. B. '09.07.2025 17:21:03'
        return {
            "id": self.id,
            "timestamp_utc": utc_iso,
            "timestamp": local_str,
            "log_level": self.log_level,
            "user_id": self.user_id,
            "username": self.username,
            "feature": self.feature,
            "event": self.event,
            "reference_id": self.reference_id,
            "message": self.message,
        }
