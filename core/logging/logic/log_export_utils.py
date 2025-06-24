"""
log_export_utils.py

Stellt Funktionen zur Verfügung, um Logs aus dem System in verschiedene Formate zu exportieren
und den Ausdruck von Logdaten zu steuern.

Diese Datei kapselt JSON-Export und Druck-Logik, damit GUI und Logik sauber bleiben.
"""

import json
import tempfile
import subprocess
import platform
import os
from typing import List, Dict

def export_logs_to_json(logs: List[Dict], file_path: str):
    """
    Exportiert eine Liste von Log-Dictionaries in eine formatierte JSON-Datei.

    :param logs: Liste von Logs als Dictionaries
    :param file_path: Pfad, unter dem die JSON-Datei gespeichert wird
    """
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2)

def print_logs(logs: List[Dict], format_timestamp_func):
    """
    Druckt Logs als mehrzeilige, übersichtliche Blöcke auf dem Standarddrucker.

    :param logs: Liste von Logs als Dictionaries
    :param format_timestamp_func: Funktion zum Formatieren von UTC-Zeitstempeln in lokale Strings
    """
    logs_text = []
    for log in logs:
        logs_text.append(
            f"Timestamp: {format_timestamp_func(log['timestamp'])}\n"
            f"User: {log.get('username') or f'ID:{log.get('user_id')}' or 'Unknown'}\n"
            f"Feature: {log['feature']}\n"
            f"Event: {log['event']}\n"
            f"Reference ID: {log.get('reference_id', '')}\n"
            f"Message: {log.get('message', '')}\n"
            f"Level: {log['log_level']}\n"
            + ("-" * 40) + "\n"
        )
    content = "".join(logs_text)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8") as tmp_file:
        tmp_file.write(content)
        tmp_filename = tmp_file.name

    try:
        if platform.system() == "Windows":
            subprocess.run(["notepad.exe", "/p", tmp_filename], check=True)
        elif platform.system() == "Darwin":
            subprocess.run(["lp", tmp_filename], check=True)
        else:
            subprocess.run(["lp", tmp_filename], check=True)
    finally:
        try:
            os.unlink(tmp_filename)
        except Exception:
            pass
