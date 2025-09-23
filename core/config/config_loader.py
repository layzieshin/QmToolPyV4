"""
Backward-compatible wrapper delegating to :mod:`config_service`.

Diese Version stellt ALLE Legacy-Erwartungen bereit, die u. a. der
Settings-Tab nutzt:
- _config : ConfigParser der machine-INI (lesbar/schreibbar)
- _load_config() : Reload der machine-INI
- INI_PATH : Path (für .open/.read_text)
- _DEFAULT_INI_CONTENT : dict[section][key] -> value

Zusätzlich:
- Path-Konstanten (QM_DB_PATH, LOG_DB_PATH, ...)
- String-Aliasse (QM_DB_PATH_STR, ...)
- DEFAULTS_PATH bleibt als String (GUI-freundlich) + *_T als Path
"""
from __future__ import annotations

import io
import configparser
from pathlib import Path
from threading import RLock
from typing import Dict

from .config_service import (
    ConfigService,
    config_service,
    PROJECT_ROOT,
    DEFAULTS_INI,
    MACHINE_INI,
    _DEFAULTS,          # in-memory fallback defaults
)

__all__ = [
    # Wrapper / Singleton
    "ConfigLoader",
    "config_loader",

    # Legacy Path-Konstanten (für bestehenden Code, z. B. .as_posix())
    "QM_DB_PATH",
    "LOG_DB_PATH",
    "MODULES_JSON_PATH",
    "LABELS_TSV_PATH",

    # String-Aliasse (GUI/Tkinter)
    "QM_DB_PATH_STR",
    "LOG_DB_PATH_STR",
    "MODULES_JSON_PATH_STR",
    "LABELS_TSV_PATH_STR",

    # INI/Defaults (beides anbieten: String & Path)
    "PROJECT_ROOT_PATH_T",
    "DEFAULTS_PATH_T",
    "INI_PATH_T",
    "PROJECT_ROOT_PATH",
    "DEFAULTS_PATH",
    "INI_PATH",
    "INI_PATH_STR",

    # Inhalt der defaults.ini als dict (für Settings-Tab)
    "_DEFAULT_INI_CONTENT",
]


# ----------------------------- helpers ----------------------------- #
def _read_ini_file(path: Path) -> configparser.ConfigParser:
    cp = configparser.ConfigParser()
    if path.exists():
        cp.read(path, encoding="utf-8")
    return cp


def _cp_to_dict(cp: configparser.ConfigParser) -> Dict[str, Dict[str, str]]:
    data: Dict[str, Dict[str, str]] = {}
    for section in cp.sections():
        data[section] = {k: v for k, v in cp.items(section)}
    return data


def _defaults_ini_as_dict() -> Dict[str, Dict[str, str]]:
    """
    Liefert defaults.ini als dict; wenn Datei fehlt, synthetisieren wir
    sie aus den in-memory _DEFAULTS.
    """
    if DEFAULTS_INI.exists():
        cp = _read_ini_file(DEFAULTS_INI)
        return _cp_to_dict(cp)

    # Fallback aus _DEFAULTS (in-memory)
    cp = configparser.ConfigParser()
    cp.read_dict(_DEFAULTS)
    return _cp_to_dict(cp)


# -------------------------- main wrapper -------------------------- #
class ConfigLoader:
    """
    Dünner Legacy-Wrapper um :class:`ConfigService`.

    WICHTIG für Legacy-GUI:
    - self._config: ConfigParser mit Inhalt der MACHINE_INI
    - self._load_config(): lädt MACHINE_INI neu in _config
    """
    _instance: "ConfigLoader | None" = None
    _lock = RLock()

    def __new__(cls) -> "ConfigLoader":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._service = config_service
                # machine-INI in _config vorhalten (GUI greift darauf zu)
                cls._instance._config = _read_ini_file(MACHINE_INI)
            return cls._instance

    # ----------------- Legacy-API (Paths zurückgeben) ----------------- #
    def get_qm_db_path(self) -> Path:
        return self._service.database.qm_tool

    def get_logging_db_path(self) -> Path:
        return self._service.database.logging

    def get_modules_json_path(self) -> Path:
        return self._service.files.modules_json

    def get_labels_tsv_path(self) -> Path:
        return self._service.files.labels_tsv

    # ----------------- Synonyme mit *_t (ebenfalls Path) --------------- #
    def get_qm_db_path_t(self) -> Path:
        return self.get_qm_db_path()

    def get_logging_db_path_t(self) -> Path:
        return self.get_logging_db_path()

    def get_modules_json_path_t(self) -> Path:
        return self.get_modules_json_path()

    def get_labels_tsv_path_t(self) -> Path:
        return self.get_labels_tsv_path()

    # ----------------- Meta-Infos ------------------------------------- #
    def get_app_name(self) -> str:
        return self._service.general.app_name

    def get_version(self) -> str:
        return self._service.general.version

    # ----------------- Legacy internals für GUI ----------------------- #
    def _load_config(self) -> None:
        """
        Reload der MACHINE_INI in den in-memory ConfigParser.
        (Wird vom Settings-Tab nach Restore benutzt.)
        """
        self._config = _read_ini_file(MACHINE_INI)
        # Optional: zusammen mit den Services neu laden, falls gewünscht:
        # self._service.reload()


# ------------------------- Singletons/Konstanten ------------------------- #
config_loader: ConfigLoader = ConfigLoader()

# Getypte (Path) Exporte für Alt-Code
QM_DB_PATH: Path = config_loader.get_qm_db_path()
LOG_DB_PATH: Path = config_loader.get_logging_db_path()
MODULES_JSON_PATH: Path = config_loader.get_modules_json_path()
LABELS_TSV_PATH: Path = config_loader.get_labels_tsv_path()

# String-Aliasse für GUI/Tkinter
QM_DB_PATH_STR: str = str(QM_DB_PATH)
LOG_DB_PATH_STR: str = str(LOG_DB_PATH)
MODULES_JSON_PATH_STR: str = str(MODULES_JSON_PATH)
LABELS_TSV_PATH_STR: str = str(LABELS_TSV_PATH)

# Projekt-/INI-Pfade
PROJECT_ROOT_PATH_T: Path = PROJECT_ROOT
DEFAULTS_PATH_T: Path = DEFAULTS_INI
INI_PATH_T: Path = MACHINE_INI

# Von der GUI oft als String genutzt:
PROJECT_ROOT_PATH: str = str(PROJECT_ROOT_PATH_T)   # nur Info/Anzeige
DEFAULTS_PATH: str = str(DEFAULTS_PATH_T)           # STRING belassen
INI_PATH: Path = INI_PATH_T                         # WICHTIG: Path für .open/.read_text
INI_PATH_STR: str = str(INI_PATH_T)

# Inhalt der defaults.ini als DICT (Settings-Tab erwartet .get())
_DEFAULT_INI_CONTENT: Dict[str, Dict[str, str]] = _defaults_ini_as_dict()
