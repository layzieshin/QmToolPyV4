"""
ClockService – timezone-aware clock formatting with small UX niceties.
Separated from the view to keep responsibilities clean.
"""

from __future__ import annotations

from datetime import datetime

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore


class ClockService:
    """Formats time and date with optional blinking colon."""

    def now_localized(self, tz_name: str) -> datetime:
        if ZoneInfo:
            try:
                return datetime.now(ZoneInfo(tz_name))
            except Exception:
                return datetime.now()
        return datetime.now()

    @staticmethod
    def _time_format(use_24h: bool, show_seconds: bool) -> str:
        if use_24h:
            return "%H:%M:%S" if show_seconds else "%H:%M"
        return "%I:%M:%S %p" if show_seconds else "%I:%M %p"

    def format(
        self,
        *,
        timezone: str,
        use_24h: bool,
        show_seconds: bool,
        show_date: bool,
        date_format: str,
        blink_colon: bool,
        blink_state: bool,
    ) -> tuple[str, str]:
        now = self.now_localized(timezone)
        fmt = self._time_format(use_24h, show_seconds)
        time_text = now.strftime(fmt)
        if blink_colon and not blink_state:
            time_text = time_text.replace(":", " ")
        date_text = now.strftime(date_format) if show_date else ""
        return time_text, date_text
