"""
log_export_utils.py

Exportiert Logdaten als JSON-Datei oder druckt sie.
"""

import json
import platform
import tempfile
import subprocess
from tkinter import messagebox

def export_logs_to_json(logs, filepath):
    data = [log.to_dict() for log in logs]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def print_file(filepath):
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.run(['notepad.exe', '/p', filepath], check=True)
        elif system == "Darwin":
            subprocess.run(['lp', filepath], check=True)
        else:
            subprocess.run(['lp', filepath], check=True)
    except Exception as e:
        messagebox.showerror("Druckfehler", f"Drucken fehlgeschlagen: {e}")
