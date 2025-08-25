"""
Data model for Clockwork settings.
"""

from dataclasses import dataclass


@dataclass
class ClockworkSettings:
    """
    Encapsulates all user-configurable options for the clock widget.

    Attributes:
        timezone (str): IANA timezone name (e.g., "Europe/Berlin").
        show_seconds (bool): Whether to render seconds.
        use_24h (bool): 24-hour clock if True, 12-hour with AM/PM if False.
        show_date (bool): Whether to render the date line.
        date_format (str): Python strftime format for the date line.
        blink_colon (bool): Blink the time separator (cosmetic).
        update_interval_ms (int): Update cadence in milliseconds.
    """
    timezone: str = "Europe/Berlin"
    show_seconds: bool = True
    use_24h: bool = True
    show_date: bool = True
    date_format: str = "%Y-%m-%d"
    blink_colon: bool = False
    update_interval_ms: int = 250

    def time_format(self) -> str:
        """
        Returns a strftime format string for the time line based on flags.

        Returns:
            str: Format such as "%H:%M:%S" or "%I:%M %p".
        """
        if self.use_24h:
            return "%H:%M:%S" if self.show_seconds else "%H:%M"
        # 12h with AM/PM
        return "%I:%M:%S %p" if self.show_seconds else "%I:%M %p"
