"""
log_export_utils.py

Minimal-Variante: nur noch Export in eine JSON-Datei.

• export_logs_to_json(logs, filepath)
• dump_logs_to_temp_json(logs)         → gibt den Temp-Pfad zurück
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import List


def export_logs_to_json(logs: List[dict], filepath: str | Path) -> None:
    """Write *logs* to *filepath* as UTF-8 JSON (pretty-printed)."""
    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(logs, fh, indent=4, ensure_ascii=False)


def dump_logs_to_temp_json(logs: List[dict]) -> Path:
    """Create a temp JSON file (for mail attachments, bug reports, …)."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump(logs, tmp, indent=4, ensure_ascii=False)
    tmp.close()
    return Path(tmp.name)
