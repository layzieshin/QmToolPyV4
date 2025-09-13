"""core/config/config_service.py
================================

Typed, layered configuration service.

Loads configuration values from multiple layers with clear precedence:

Layer 0: hard coded defaults (dataclasses)
Layer 1: defaults.ini (repository, read only)
Layer 2: environment variables (prefix ``QMTOOL_`` with ``SECTION__KEY``)
Layer 3: machine config ``core/config/config.ini``
Layer 4: user overrides ``~/.config/qmtool/config.ini``

The service exposes typed attributes for known sections and keeps
track of where each value originated from.  Values are validated and
converted to their respective types.

This module keeps external dependencies at zero and only relies on
stdlib modules.
"""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PureWindowsPath
from typing import Dict, Tuple

# ---------------------------------------------------------------------------
#  Root paths
# ---------------------------------------------------------------------------


def _find_project_root() -> Path:
    """Walk upwards until a folder containing ``core`` is found."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "core").is_dir():
            return parent
    return here.parent


PROJECT_ROOT = _find_project_root()
CONFIG_DIR = PROJECT_ROOT / "core" / "config"
DATABASE_DIR = PROJECT_ROOT / "databases"
DEFAULTS_PATH = CONFIG_DIR / "defaults.ini"
MACHINE_CONFIG_PATH = CONFIG_DIR / "config.ini"
# User config: ~/.config/qmtool/config.ini  (very small cross-platform helper)
USER_CONFIG_DIR = Path(os.getenv("APPDATA" or "")) if os.name == "nt" else Path(
    os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")
)
USER_CONFIG_DIR = USER_CONFIG_DIR / "QMTool" if os.name == "nt" else USER_CONFIG_DIR / "qmtool"
USER_CONFIG_PATH = USER_CONFIG_DIR / "config.ini"


# ---------------------------------------------------------------------------
#  Dataclasses for typed access
# ---------------------------------------------------------------------------


def _path(value: str) -> Path:
    raw = Path(value).expanduser()
    if raw.is_absolute() or PureWindowsPath(value).is_absolute():
        return raw
    return (PROJECT_ROOT / raw).resolve()


def _bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


@dataclass
class DatabaseSettings:
    qm_tool: Path = _path("databases/qm-tool.db")
    logging: Path = _path("databases/logs.db")


@dataclass
class GeneralSettings:
    app_name: str = ""
    version: str = ""
    debug_db_paths: bool = False


@dataclass
class FilesSettings:
    modules_json: Path = _path("core/config/modules.json")
    labels_tsv: Path = _path("core/config/labels.tsv")


@dataclass
class FeaturesSettings:
    enable_document_signer: bool = False
    enable_workflow_manager: bool = False


class Layer(Enum):
    DEFAULT = 0
    DEFAULT_FILE = 1
    ENVIRONMENT = 2
    MACHINE = 3
    USER = 4


class ConfigService:
    """Central access point for merged, typed configuration values."""

    def __init__(self) -> None:
        self.database = DatabaseSettings()
        self.general = GeneralSettings()
        self.files = FilesSettings()
        self.features = FeaturesSettings()

        # (section, key) -> (Layer, source description)
        self._sources: Dict[Tuple[str, str], Tuple[Layer, str]] = {}

        self._ensure_machine_ini()
        self._load()

    # ------------------------------------------------------------------
    #  Loading helpers
    # ------------------------------------------------------------------

    def _ensure_machine_ini(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not MACHINE_CONFIG_PATH.exists() and DEFAULTS_PATH.exists():
            MACHINE_CONFIG_PATH.write_text(DEFAULTS_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    def _record(self, section: str, key: str, layer: Layer, source: str) -> None:
        self._sources[(section.lower(), key.lower())] = (layer, source)

    def _apply(self, section: str, key: str, value: str, layer: Layer, source: str) -> None:
        sec = section.lower()
        k = key.lower()
        if sec == "database":
            if k == "qm_tool":
                self.database.qm_tool = _path(value)
            elif k == "logging":
                self.database.logging = _path(value)
        elif sec == "general":
            if k == "app_name":
                self.general.app_name = value
            elif k == "version":
                self.general.version = value
            elif k == "debug_db_paths":
                self.general.debug_db_paths = _bool(value)
        elif sec == "files":
            if k == "modules_json":
                self.files.modules_json = _path(value)
            elif k == "labels_tsv":
                self.files.labels_tsv = _path(value)
        elif sec == "features":
            if k == "enable_document_signer":
                self.features.enable_document_signer = _bool(value)
            elif k == "enable_workflow_manager":
                self.features.enable_workflow_manager = _bool(value)
        self._record(section, key, layer, source)

    def _load_file(self, path: Path, layer: Layer) -> None:
        if not path.exists():
            return
        parser = configparser.ConfigParser()
        parser.read(path, encoding="utf-8")
        for section in parser.sections():
            for key, value in parser.items(section):
                self._apply(section, key, value, layer, str(path))

    def _load_env(self, layer: Layer) -> None:
        prefix = "QMTOOL_"
        for env_key, value in os.environ.items():
            if not env_key.startswith(prefix):
                continue
            tail = env_key[len(prefix) :]
            if "__" not in tail:
                continue
            section, key = tail.split("__", 1)
            self._apply(section, key, value, layer, f"env:{env_key}")

    def _load(self) -> None:
        self._load_file(DEFAULTS_PATH, Layer.DEFAULT_FILE)
        self._load_env(Layer.ENVIRONMENT)
        self._load_file(MACHINE_CONFIG_PATH, Layer.MACHINE)
        self._load_file(USER_CONFIG_PATH, Layer.USER)

    # ------------------------------------------------------------------
    #  Public helpers
    # ------------------------------------------------------------------

    def meta_source(self, section: str, key: str) -> Tuple[Layer, str] | None:
        """Return the source layer and description for ``section/key``."""
        return self._sources.get((section.lower(), key.lower()))


# Global instance -------------------------------------------------------------
config_service = ConfigService()

