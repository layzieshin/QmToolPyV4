"""
core/config/config_loader.py
============================

Zentraler Konfigurations-Loader (Singleton).

• Sucht das Projekt-Root dynamisch (Verzeichnis mit »core«-Ordner).
• Legt *config.ini* bei Bedarf automatisch unter  <root>/core/config  an.
• Liefert Pfade zu qm_tool.db & logs.db (liegen unter  <root>/databases).
• Stellt Getter für App-Name & Version bereit (Read-Only).
• Keine Schreib-API – die INI wird bewusst manuell gepflegt.

Diese Datei hält sich an unsere Projekt-Konventionen:
    – Single Responsibility
    – Klare Docstrings + Kommentare
    – Keine externen Abhängigkeiten außer stdlib
"""

from __future__ import annotations

import configparser
from pathlib import Path
from threading import RLock


# --------------------------------------------------------------------------- #
#  Root- und Pfadermittlung
# --------------------------------------------------------------------------- #
def _find_project_root() -> Path:
    """
    Geht von diesem File nach oben, bis ein Ordner *core* gefunden wird.
    Das ist unser Projekt-Root.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "core").is_dir():
            return parent
    # Fallback: ein Verzeichnis oberhalb (sollte quasi nie passieren)
    return here.parent


PROJECT_ROOT = _find_project_root()                        # <root>
CONFIG_DIR = PROJECT_ROOT / "core" / "config"              # <root>/core/config
INI_PATH = CONFIG_DIR / "config.ini"                       # <root>/core/config/config.ini
DATABASE_DIR = PROJECT_ROOT / "databases"                  # <root>/databases


# --------------------------------------------------------------------------- #
#  Default-Inhalte für eine neu erzeugte config.ini
# --------------------------------------------------------------------------- #
_DEFAULT_INI_CONTENT = {
    "Database": {
        "qm_tool": str((DATABASE_DIR / "qm-tool.db").as_posix()),
        "logging": str((DATABASE_DIR / "logs.db").as_posix()),
    },
    "General": {
        "app_name": "",
        "version": "",
    },
    "Files": {
        "modules_json": str((PROJECT_ROOT / "core" / "config" / "modules.json").as_posix()),
        "labels_tsv": str((PROJECT_ROOT / "core" / "config" / "labels.tsv").as_posix()),
    },
}


# --------------------------------------------------------------------------- #
#  Interne Helfer
# --------------------------------------------------------------------------- #
def _ensure_ini_exists() -> None:
    """
    Stellt sicher, dass CONFIG_DIR & config.ini vorhanden sind.
    Wird automatisch beim ersten Zugriff auf den Singleton aufgerufen.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not INI_PATH.exists():
        parser = configparser.ConfigParser()
        parser.read_dict(_DEFAULT_INI_CONTENT)
        with INI_PATH.open("w", encoding="utf-8") as f:
            parser.write(f)


# --------------------------------------------------------------------------- #
#  ConfigLoader-Singleton
# --------------------------------------------------------------------------- #
class ConfigLoader:
    """Thread-sicherer Singleton zum Laden der config.ini."""

    _instance: "ConfigLoader | None" = None
    _lock = RLock()

    # ------------------------------------------------------------------- #
    #  Erzeugung
    # ------------------------------------------------------------------- #
    def __new__(cls) -> "ConfigLoader":
        with cls._lock:
            if cls._instance is None:
                _ensure_ini_exists()
                cls._instance = super().__new__(cls)
                cls._instance._load_config()
            return cls._instance

    # ------------------------------------------------------------------- #
    #  Init-Helpers
    # ------------------------------------------------------------------- #
    def _load_config(self) -> None:
        """Liest die INI in einen ConfigParser ein."""
        self._config = configparser.ConfigParser()
        self._config.read(INI_PATH, encoding="utf-8")

    # ------------------------------------------------------------------- #
    #  Öffentliche Getter
    # ------------------------------------------------------------------- #
    def get_qm_db_path(self) -> Path:
        """Pfad zur Haupt­datenbank (qm_tool.db)."""
        return Path(
            self._config.get(
                "Database", "qm_tool", fallback=_DEFAULT_INI_CONTENT["Database"]["qm_tool"]
            )
        ).expanduser()

    def get_logging_db_path(self) -> Path:
        """Pfad zur Logging-Datenbank (logs.db)."""
        return Path(
            self._config.get(
                "Database", "logging", fallback=_DEFAULT_INI_CONTENT["Database"]["logging"]
            )
        ).expanduser()

    def get_app_name(self) -> str:
        """Anwendungs-Name (optional, leer möglich)."""
        return self._config.get(
            "General", "app_name", fallback=_DEFAULT_INI_CONTENT["General"]["app_name"]
        )

    def get_version(self) -> str:
        """Versions­nummer (optional, leer möglich)."""
        return self._config.get(
            "General", "version", fallback=_DEFAULT_INI_CONTENT["General"]["version"]
        )

    def get_modules_json_path(self) -> Path:
        return Path(self._config.get(
            "Files", "modules_json", fallback=_DEFAULT_INI_CONTENT["Files"]["modules_json"]
        )).expanduser()

    def get_labels_tsv_path(self) -> Path:
        return Path(self._config.get(
            "Files", "labels_tsv", fallback=_DEFAULT_INI_CONTENT["Files"]["labels_tsv"]
        )).expanduser()


# --------------------------------------------------------------------------- #
#  Globale Instanz für bequemen Zugriff
# --------------------------------------------------------------------------- #
config_loader: ConfigLoader = ConfigLoader()  # pylint: disable=invalid-name
QM_DB_PATH: Path = config_loader.get_qm_db_path()
LOG_DB_PATH: Path = config_loader.get_logging_db_path()
MODULES_JSON_PATH = config_loader.get_modules_json_path()
LABELS_TSV_PATH   = config_loader.get_labels_tsv_path()
