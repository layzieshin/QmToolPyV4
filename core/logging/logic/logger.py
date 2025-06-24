"""
logger.py

Einfaches, konsolenbasiertes Logging-Modul.

- Ermöglicht das Speichern von Logeinträgen mit Zeit, Feature, Event und User.
- Loggt standardmäßig auf der Konsole.
- Die Logeinträge können später in eine Datenbank oder Datei erweitert werden.
"""

import datetime

class Logger:
    """
    Logger-Klasse zur Verwaltung und Ausgabe von Logeinträgen.
    """

    def __init__(self):
        self.entries = []

    def log(self, feature: str, event: str, user: dict | None = None):
        """
        Erzeugt und speichert einen Logeintrag.

        :param feature: Name des Features oder Moduls
        :param event: Beschreibung des Ereignisses
        :param user: Optionales Benutzer-Dict mit mindestens 'username'
        """
        entry = {
            "time": datetime.datetime.utcnow().isoformat(),
            "feature": feature,
            "event": event,
            "user": user.get("username") if user else "unknown"
        }
        self.entries.append(entry)
        print(f"[LOG] {entry}")

# Singleton-Instanz für globalen Zugriff
logger = Logger()
