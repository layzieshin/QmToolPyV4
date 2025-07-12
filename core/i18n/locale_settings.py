"""
locale_settings.py

Definiert das Settings-Schema für die App-Sprache.
Wird von SettingsView als eigener Tab "App" eingebunden.
"""

SETTINGS_SCHEMA = [
    {
        "key": "language",
        "label": "App-Sprache",
        "type": "enum",
        "options": ["de", "en"],
        "default": "de",
        "scope": "both",          # global + user override
    }
]
