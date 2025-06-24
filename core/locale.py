"""
locale.py

Einfacher Übersetzungsmanager für mehrsprachige UI-Texte.

- Unterstützt Schlüssel-basiertes Übersetzen
- Aktuell nur Deutsch implementiert, Erweiterung möglich
"""

class LocaleManager:
    def __init__(self, lang="de"):
        self.lang = lang
        self.strings = {
            "de": {
                "load_config": "Config laden",
                "log_event": "Ereignis loggen",
                "auth_check": "Login-Status prüfen",
                "show_time": "Zeit anzeigen"
            }
        }

    def t(self, key: str) -> str:
        """
        Übersetzt einen Schlüssel in die aktuelle Sprache.

        :param key: Schlüsselstring
        :return: Übersetzter Text oder der Schlüssel selbst, falls nicht gefunden
        """
        return self.strings.get(self.lang, {}).get(key, key)

# Singleton-Instanz für globale Nutzung
locale = LocaleManager()
