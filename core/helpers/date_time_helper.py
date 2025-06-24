"""
date_time_helper.py

Hilfsfunktionen zur Zeiterfassung und Zeitzonen-Umwandlung.

- Stellt UTC-Zeit im ISO-Format bereit.
"""

from datetime import datetime, timezone

def utc_now() -> str:
    """
    Gibt die aktuelle UTC-Zeit als ISO-Format-String zurück.

    :return: Zeitstring im Format 'YYYY-MM-DD HH:MM:SS UTC'
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
