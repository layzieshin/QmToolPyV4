"""
date_time_helpers.py

Provides helper functions for conversion and formatting of date and time values,
with special focus on UTC and Europe/Berlin timezone handling for logging and display.

All features and modules should use ONLY these helpers for date/time logic.
"""

from datetime import datetime, date, time, timezone

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    raise ImportError("Python 3.9+ with zoneinfo is required for timezone support.")

# Local timezone for display (can be made configurable)
LOCAL_TZ = ZoneInfo("Europe/Berlin")

def utc_now_iso() -> str:
    """
    Returns the current UTC time as an ISO8601 string (YYYY-MM-DDTHH:MM:SS+00:00).
    Used for logging and DB storage.
    """
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def local_date_to_utc_range(start: date, end: date):
    """
    Converts local start and end dates (as date objects) to UTC datetime range strings.
    Used for filtering DB entries over full days, respecting local time.

    :param start: Start date (local)
    :param end: End date (local)
    :return: (start_utc_iso, end_utc_iso)
    """
    local_start = datetime.combine(start, time.min).replace(tzinfo=LOCAL_TZ)
    local_end = datetime.combine(end, time.max).replace(tzinfo=LOCAL_TZ)
    start_utc = local_start.astimezone(timezone.utc)
    end_utc = local_end.astimezone(timezone.utc)
    return start_utc.isoformat(), end_utc.isoformat()

def utc_to_local_str(utc_iso: str) -> str:
    """
    Formats a UTC ISO8601 timestamp as a localized, human-readable string for display.

    :param utc_iso: UTC time as ISO string (from DB/logs)
    :return: String in format "DD.MM.YYYY HH:mm:ss" (local time)
    """
    dt_utc = datetime.fromisoformat(utc_iso)
    dt_local = dt_utc.astimezone(LOCAL_TZ)
    return dt_local.strftime("%d.%m.%Y %H:%M:%S")

def local_to_utc_iso(dt_local: datetime) -> str:
    """
    Converts a local datetime to a UTC ISO string.
    """
    if dt_local.tzinfo is None:
        dt_local = dt_local.replace(tzinfo=LOCAL_TZ)
    dt_utc = dt_local.astimezone(timezone.utc)
    return dt_utc.replace(microsecond=0).isoformat()

def utc_iso_to_local_datetime(utc_iso: str) -> datetime:
    """
    Converts a UTC ISO string to a local datetime object.
    """
    dt_utc = datetime.fromisoformat(utc_iso)
    return dt_utc.astimezone(LOCAL_TZ)

# More helpers can be added as needed (e.g., custom formatting, parsing, etc.)

