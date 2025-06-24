"""
config_loader.py

Zentrales Modul zum Laden, Schreiben und Initialisieren der Konfigurationsdatei config.ini.

- Lädt die config.ini aus dem config-Verzeichnis (unterhalb des Projektwurzelverzeichnisses).
- Legt eine Standard-Konfigurationsdatei an, falls keine existiert.
- Bietet Methoden zum sicheren Lesen, Schreiben und Speichern von Konfigurationseinträgen.
- Unterstützt boolsche und numerische Werte mit komfortablen Helfermethoden.
- Ermöglicht dynamisches Setzen von Default-Werten beim erstmaligen Zugriff.
"""

from pathlib import Path
import configparser

# Pfad zum aktuellen Skript und Projektwurzel (ein Verzeichnis oberhalb des aktuellen)
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[1]

# Pfad zum config-Ordner und der config.ini
CONFIG_DIR = PROJECT_ROOT / "config"
CONFIG_PATH = CONFIG_DIR / "config.ini"

# Vordefinierte Standardwerte für die Konfigurationsdatei
DEFAULT_CONFIG = {
    "Database": {
        "qm_tool": str((PROJECT_ROOT / "databases" / "qm-tool.db").as_posix()),
        "logging": str((PROJECT_ROOT / "databases" / "logging.db").as_posix())
    },
    "General": {
        "app_name": "QM-Tool",
        "version": "2.0"
    },
    "Features": {
        "enable_document_signer": "true",
        "enable_workflow_manager": "true"
    }
}


class ConfigLoader:
    """
    Singleton-Klasse zum zentralen Management der config.ini.

    - Stellt Methoden zur Verfügung, um Konfigurationswerte sicher auszulesen und zu setzen.
    - Schreibt neue oder geänderte Werte bei Bedarf zurück in die Datei.
    - Stellt sicher, dass die config.ini beim ersten Start mit sinnvollen Defaults existiert.
    """

    def __init__(self, config_path=CONFIG_PATH):
        """
        Initialisiert den ConfigLoader.
        Lädt bestehende config.ini oder legt eine mit Default-Werten an.
        """
        self.config_path = config_path
        self.config = configparser.ConfigParser()
        self._ensure_config_exists()
        self._load_config()

    def _ensure_config_exists(self):
        """
        Prüft, ob die config.ini existiert.
        Falls nicht, wird die Datei mit DEFAULT_CONFIG und das Verzeichnis angelegt.
        """
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not self.config_path.exists():
            # Standard-Konfigurationsdatei schreiben
            for section, values in DEFAULT_CONFIG.items():
                self.config[section] = values
            with self.config_path.open("w", encoding="utf-8") as configfile:
                self.config.write(configfile)

    def _load_config(self):
        """
        Lädt die Konfigurationswerte aus der config.ini in das interne Parser-Objekt.
        """
        self.config.read(self.config_path, encoding="utf-8")

    def get_config_value(self, section: str, key: str, fallback=None) -> str | None:
        """
        Gibt den Wert eines Schlüssels aus einer Sektion zurück.
        Falls der Schlüssel oder die Sektion nicht existiert, wird 'fallback' zurückgegeben.

        :param section: Name der Sektion
        :param key: Schlüsselname
        :param fallback: Rückgabewert, wenn key nicht vorhanden
        :return: Wert als String oder fallback
        """
        return self.config.get(section, key, fallback=fallback)

    def get_bool(self, section: str, key: str, fallback: bool = False) -> bool:
        """
        Spezielles Auslesen von Booleschen Werten aus der Konfig.
        Gibt den booleschen Wert zurück oder fallback, falls nicht gefunden oder Fehler.

        :param section: Name der Sektion
        :param key: Schlüsselname
        :param fallback: Rückgabewert falls nicht vorhanden
        :return: Boolean-Wert
        """
        try:
            return self.config.getboolean(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback

    def get_int(self, section: str, key: str, fallback: int = 0) -> int:
        """
        Spezielles Auslesen von Integer-Werten aus der Konfig.
        Gibt den int-Wert zurück oder fallback, falls nicht gefunden oder Fehler.

        :param section: Name der Sektion
        :param key: Schlüsselname
        :param fallback: Rückgabewert falls nicht vorhanden
        :return: Integer-Wert
        """
        try:
            return self.config.getint(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback

    def get_or_set_default(self, section: str, key: str, default) -> str:
        """
        Gibt den Wert zurück oder setzt ihn auf default, wenn nicht vorhanden.
        Schreibt neue Werte direkt zurück in die Datei.

        :param section: Name der Sektion
        :param key: Schlüsselname
        :param default: Wert, der gesetzt wird falls key fehlt
        :return: Wert als String
        """
        if not self.config.has_section(section):
            self.config.add_section(section)

        if not self.config.has_option(section, key):
            self.config.set(section, key, str(default))
            self.save_config()
            return str(default)
        else:
            return self.config.get(section, key)

    def set_config_value(self, section: str, key: str, value) -> None:
        """
        Setzt einen Wert in der Konfiguration (im Speicher).
        Die Änderung wird erst mit save_config() dauerhaft.

        :param section: Name der Sektion (wird ggf. neu angelegt)
        :param key: Schlüsselname
        :param value: Neuer Wert (wird als String gespeichert)
        """
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, str(value))

    def save_config(self) -> None:
        """
        Schreibt die aktuelle Konfiguration in die config.ini-Datei.
        """
        with self.config_path.open("w", encoding="utf-8") as configfile:
            self.config.write(configfile)

    def reload(self) -> None:
        """
        Lädt die Konfiguration neu von der config.ini.
        Nützlich, wenn externe Änderungen an der Datei vorgenommen wurden.
        """
        self._load_config()


# Globale Instanz des ConfigLoaders zur Nutzung im gesamten Projekt
config_loader = ConfigLoader()
