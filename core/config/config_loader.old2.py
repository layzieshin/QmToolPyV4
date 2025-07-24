"""
core/config/config_loader.py

Zentrale Konfigurationsverwaltung mit persistentem Speicher in einer SQLite-Datenbank
und optionalem Fallback zur INI-Datei. Beinhaltet Debug-Flag vor Initialisierung.
"""
from __future__ import annotations

import configparser
from pathlib import Path
from threading import RLock
from typing import Final

HERE = Path(__file__).resolve().parent
INI_PATH = HERE / "config.ini"
PROJECT_ROOT = HERE.parents[1]

# ------------------------------------------------------------------
#  Debug-Modus FRÜH einlesen – unabhängig vom ConfigLoader
# ------------------------------------------------------------------
def _early_debug_flag() -> bool:
    if not INI_PATH.exists():
        return False
    parser = configparser.ConfigParser()
    parser.read(INI_PATH, encoding="utf-8")
    try:
        return parser.getboolean("General", "debug_db_paths", fallback=False)
    except Exception:
        return False

DEBUG_DB: Final[bool] = _early_debug_flag()

# ------------------------------------------------------------------
#  Standardwerte
# ------------------------------------------------------------------
DEFAULTS: dict[str, dict[str, str]] = {
    "Database": {
        "qm_tool": str((PROJECT_ROOT / "databases" / "qm-tool.db").as_posix()),
        "logging": str((PROJECT_ROOT / "databases" / "logging.db").as_posix()),
    },
    "General": {
        "app_name": "QM-Tool",
        "version": "2.0",
        "enable_ini_fallback": "true",
        "debug_db_paths": "false",
    },
    "Features": {
        "enable_document_signer": "true",
        "enable_workflow_manager": "true",
    },
}

# Repository import erst nach Auflösung
from core.config.config_repository import ConfigRepository

# ------------------------------------------------------------------
#  DB-Pfad auflösen
# ------------------------------------------------------------------
def _resolve_db_path() -> Path:
    parser = configparser.ConfigParser()
    if INI_PATH.exists():
        parser.read(INI_PATH, encoding="utf-8")
        ini_enabled = (
            parser.getboolean("General", "enable_ini_fallback", fallback=True)
            if parser.has_section("General") else True
        )
        if ini_enabled and parser.has_option("Database", "qm_tool"):
            return Path(parser.get("Database", "qm_tool")).expanduser()
    return Path(DEFAULTS["Database"]["qm_tool"]).expanduser()

_DB_PATH: Final[Path] = _resolve_db_path()

# ------------------------------------------------------------------
#  ConfigLoader Singleton
# ------------------------------------------------------------------
class ConfigLoader:
    _instance: ConfigLoader | None = None
    _lock = RLock()

    @classmethod
    def instance(cls) -> ConfigLoader:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        self.repo = ConfigRepository.instance(_DB_PATH)
        self._sync_from_ini_if_needed()
        self._mandatory_check()
        if DEBUG_DB:
            print(f"[DEBUG] QM-Tool DB \u279e {self.repo.db_path}")

    def get(self, section: str, key: str, fallback=None) -> str | None:
        return self.repo.get(section, key, fallback)

    def get_bool(self, section: str, key: str, fallback: bool = False) -> bool:
        return self.repo.get_bool(section, key, fallback)

    def get_int(self, section: str, key: str, fallback: int = 0) -> int:
        return self.repo.get_int(section, key, fallback)

    def set(self, section: str, key: str, value) -> None:
        self.repo.set(section, key, value)
        if self.get_bool("General", "enable_ini_fallback", True):
            self._write_to_ini(section, key, value)

    def get_qm_db_path(self) -> Path:
        return self.repo.db_path

    def _sync_from_ini_if_needed(self):
        if not INI_PATH.exists():
            return
        if not self.get_bool("General", "enable_ini_fallback", True):
            return
        parser = configparser.ConfigParser()
        parser.read(INI_PATH, encoding="utf-8")
        for section in parser.sections():
            for key, val in parser.items(section):
                if self.repo.get(section, key) is None:
                    self.repo.set(section, key, val)

    def _write_to_ini(self, section: str, key: str, value):
        parser = configparser.ConfigParser()
        if INI_PATH.exists():
            parser.read(INI_PATH, encoding="utf-8")
        if not parser.has_section(section):
            parser.add_section(section)
        parser.set(section, key, str(value))
        with INI_PATH.open("w", encoding="utf-8") as f:
            parser.write(f)

    def _mandatory_check(self):
        if not self.get("Database", "qm_tool"):
            raise RuntimeError("Pfad zur QM-Datenbank fehlt. Bitte in den Einstellungen setzen.")


# Globale Instanz + Importfreundliche Konstante
config_loader = ConfigLoader.instance()
QM_DB_PATH: Final[Path] = config_loader.get_qm_db_path()