"""Typed, layered configuration loader with precedence handling."""
from __future__ import annotations

import os
import configparser
import shutil
from dataclasses import dataclass, fields
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Dict, Tuple

# --------------------------------------------------------------------------- #
#  Paths & default definitions
# --------------------------------------------------------------------------- #

def _find_project_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "core").is_dir():
            return parent
    return here.parent

PROJECT_ROOT = _find_project_root()
CONFIG_DIR = PROJECT_ROOT / "core" / "config"
DEFAULTS_INI = CONFIG_DIR / "defaults.ini"
MACHINE_INI = CONFIG_DIR / "config.ini"


_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "Database": {
        "qm_tool": (PROJECT_ROOT / "databases" / "qm-tool.db").as_posix(),
        "logging": (PROJECT_ROOT / "databases" / "logs.db").as_posix(),
    },
    "Files": {
        "modules_json": (PROJECT_ROOT / "core" / "config" / "modules.json").as_posix(),
        "labels_tsv": (PROJECT_ROOT / "core" / "config" / "labels.tsv").as_posix(),
    },
    "General": {
        "app_name": "",
        "version": "",
        "debug_db_paths": "false",
    },
    "Features": {
        "enable_document_signer": "false",
        "enable_workflow_manager": "false",
    },
}


# --------------------------------------------------------------------------- #
#  Datamodels
# --------------------------------------------------------------------------- #

@dataclass
class DatabaseConfig:
    qm_tool: Path
    logging: Path


@dataclass
class FilesConfig:
    modules_json: Path
    labels_tsv: Path


@dataclass
class GeneralConfig:
    app_name: str = ""
    version: str = ""
    debug_db_paths: bool = False


@dataclass
class FeaturesConfig:
    enable_document_signer: bool = False
    enable_workflow_manager: bool = False


@dataclass
class AppConfig:
    database: DatabaseConfig
    files: FilesConfig
    general: GeneralConfig
    features: FeaturesConfig


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #

_DEF_LOCK = RLock()


def _ensure_machine_config() -> None:
    """Ensure config directory and machine config exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not MACHINE_INI.exists():
        if DEFAULTS_INI.exists():
            shutil.copy(DEFAULTS_INI, MACHINE_INI)
        else:
            parser = configparser.ConfigParser()
            parser.read_dict(_DEFAULTS)
            with MACHINE_INI.open("w", encoding="utf-8") as fh:
                parser.write(fh)


def _cp_to_dict(cp: configparser.ConfigParser) -> Dict[str, Dict[str, Any]]:
    data: Dict[str, Dict[str, Any]] = {}
    for section in cp.sections():
        data[section] = {k: v for k, v in cp.items(section)}
    return data


def _apply(target: Dict[str, Dict[str, Any]], source: Dict[str, Dict[str, Any]],
           layer: str, origin: str,
           sources: Dict[Tuple[str, str], Dict[str, str]]) -> None:
    for section, items in source.items():
        sec = target.setdefault(section, {})
        for key, value in items.items():
            sec[key] = value
            sources[(section, key)] = {"layer": layer, "source": origin}


def _cast(value: Any, typ: type) -> Any:
    if typ is Path:
        return Path(str(value)).expanduser()
    if typ is bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    if typ is int:
        return int(value)
    if typ is float:
        return float(value)
    return typ(value)


def _build_dataclass(cls: type, data: Dict[str, Any]) -> Any:
    kwargs = {}
    for field in fields(cls):
        val = data.get(field.name, field.default)
        kwargs[field.name] = _cast(val, field.type)
    return cls(**kwargs)


def _env_overlays() -> Dict[str, Dict[str, Any]]:
    prefix = "QMTOOL_"
    result: Dict[str, Dict[str, Any]] = {}
    for env_key, value in os.environ.items():
        if not env_key.startswith(prefix):
            continue
        remainder = env_key[len(prefix):]
        parts = remainder.split("__", 1)
        if len(parts) != 2:
            continue
        section, key = parts
        section = section.title()
        key = key.lower()
        result.setdefault(section, {})[key] = value
    return result


def _user_config_path() -> Path:
    if os.name == "nt":
        appdata = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "QMTool" / "config.ini"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "qmtool" / "config.ini"


# --------------------------------------------------------------------------- #
#  ConfigService
# --------------------------------------------------------------------------- #


class ConfigService:
    """Facade merging layered configuration with type safety."""

    def __init__(self) -> None:
        self._lock = RLock()
        _ensure_machine_config()
        self.reload()

    # ------------------------------------------------------------------ #
    def reload(self) -> None:
        with self._lock:
            merged: Dict[str, Dict[str, Any]] = {}
            sources: Dict[Tuple[str, str], Dict[str, str]] = {}

            # Layer 0: embedded defaults
            _apply(merged, _DEFAULTS, "code", "embedded", sources)

            # Layer 1: defaults.ini
            if DEFAULTS_INI.exists():
                cp = configparser.ConfigParser()
                cp.read(DEFAULTS_INI, encoding="utf-8")
                _apply(merged, _cp_to_dict(cp), "defaults.ini", str(DEFAULTS_INI), sources)

            # Layer 2: environment variables
            env = _env_overlays()
            _apply(merged, env, "env", "os.environ", sources)

            # Layer 3: machine config
            if MACHINE_INI.exists():
                cp = configparser.ConfigParser()
                cp.read(MACHINE_INI, encoding="utf-8")
                _apply(merged, _cp_to_dict(cp), "machine", str(MACHINE_INI), sources)

            # Layer 4: user overrides
            user_ini = _user_config_path()
            if user_ini.exists():
                cp = configparser.ConfigParser()
                cp.read(user_ini, encoding="utf-8")
                _apply(merged, _cp_to_dict(cp), "user", str(user_ini), sources)

            self._merged = merged
            self._sources = sources

            self.database = _build_dataclass(DatabaseConfig, merged.get("Database", {}))
            self.files = _build_dataclass(FilesConfig, merged.get("Files", {}))
            self.general = _build_dataclass(GeneralConfig, merged.get("General", {}))
            self.features = _build_dataclass(FeaturesConfig, merged.get("Features", {}))

    # ------------------------------------------------------------------ #
    def get(self, section: str, key: str, *, cast: Callable[[Any], Any] | type = str) -> Any:
        val = self._merged.get(section, {}).get(key)
        if val is None:
            return None
        if isinstance(cast, type):
            return _cast(val, cast)
        return cast(val)

    def meta_source(self, section: str, key: str) -> Dict[str, str] | None:
        return self._sources.get((section, key))


# Global singleton
config_service = ConfigService()

