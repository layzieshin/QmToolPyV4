"""Typed, layered configuration loader with precedence handling and robust
path normalization/fallbacks for repository-stable operation."""
from __future__ import annotations

import os
import configparser
import shutil
from dataclasses import dataclass, is_dataclass, fields, MISSING
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Dict, Tuple, Union, get_args, get_origin, get_type_hints

#from documents.logic.word_tools import Document

# --------------------------------------------------------------------------- #
#  Paths & default definitions
# --------------------------------------------------------------------------- #
def _runtime_data_root() -> Path:
    """
    Writable per-user runtime directory.
    Windows: %APPDATA%/QMToolPy
    Linux/macOS: ~/.qmtoolpy
    """
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
        p = base / "QMToolPy"
    else:
        p = Path.home() / ".qmtoolpy"

    p.mkdir(parents=True, exist_ok=True)
    return p

def _find_project_root() -> Path:
    """
    Determine the repository/project root in a robust way.

    Why this exists:
    - The app is started from different working directories (PyCharm, CLI, tests, packaged app).
    - Using `os.getcwd()` or relying on a marker file is fragile.
    - We need a stable anchor to build absolute paths (config.ini, defaults.ini, databases, …).

    Strategy:
    1) Walk upwards from this file and search for the *known* repository layout:
       <root>/core/config/defaults.ini
    2) If not found, fall back to the classic assumption that this file lives in
       <root>/core/config/config_service.py (=> parents[2]).
    """
    here = Path(__file__).resolve()

    # 1) Preferred: detect by existing repo structure
    for parent in [here.parent, *here.parents]:
        if (parent / "core" / "config" / "defaults.ini").exists() and (parent / "core").is_dir():
            return parent

    # 2) Fallback: known relative depth (…/core/config/config_service.py)
    try:
        return here.parents[2]
    except IndexError:
        return here.parent


PROJECT_ROOT = _find_project_root()
CONFIG_DIR = PROJECT_ROOT / "core" / "config"
DEFAULTS_INI = CONFIG_DIR / "defaults.ini"
MACHINE_INI = CONFIG_DIR / "config.ini"
_RUNTIME_DATA = _runtime_data_root()
# Make anchors available to os.path.expandvars consumers
os.environ.setdefault("PROJECT_ROOT", str(PROJECT_ROOT))
os.environ.setdefault("CONFIG_DIR", str(CONFIG_DIR))

# Embedded defaults that seed new installations and serve as the base layer.
_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "Database": {
        "qm_tool": (_RUNTIME_DATA / "qm-tool.db").as_posix(),
        "logging": (_RUNTIME_DATA / "logs.db").as_posix(),
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
#  Helpers (I/O and merging)
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


def _apply(
    target: Dict[str, Dict[str, Any]],
    source: Dict[str, Dict[str, Any]],
    layer: str,
    origin: str,
    sources: Dict[Tuple[str, str], Dict[str, str]],
) -> None:
    """
    Overlay 'source' onto 'target' while capturing provenance of each value.
    """
    for section, items in source.items():
        sec = target.setdefault(section, {})
        for key, value in items.items():
            sec[key] = value
            sources[(section, key)] = {"layer": layer, "source": origin}

# --------------------------------------------------------------------------- #
#  Type-safe casting + dataclass builder
# --------------------------------------------------------------------------- #

def _cast(value: Any, typ: Any) -> Any:
    """
    Convert 'value' to the runtime type 'typ'.
    Handles Optional/Union, nested dataclasses, Path/bool/int/float/str,
    and generic collections (list/tuple/dict).
    """
    if value is None:
        return None

    if isinstance(typ, str) or typ is Any:
        return value

    origin = get_origin(typ)
    args = get_args(typ)

    # Optional[T] / Union[T, None]
    if origin is Union and type(None) in args:
        non_none = next((a for a in args if a is not type(None)), Any)
        if value in ("", None):
            return None
        return _cast(value, non_none)

    # Nested dataclasses
    if is_dataclass(typ):
        if isinstance(value, dict):
            return _build_dataclass(typ, value)
        return value

    # Concrete primitives and common types
    if typ is Path:
        expanded = os.path.expandvars(str(value))
        return Path(os.path.expanduser(expanded))

    if typ is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        s = str(value).strip().lower()
        return s in {"1", "true", "yes", "y", "on"}

    if typ is int:
        if isinstance(value, bool):
            return 1 if value else 0
        return int(value)

    if typ is float:
        return float(value)

    if typ is str:
        return str(value)

    # Collections with typing generics
    if origin in (list, tuple):
        inner = args[0] if args else Any
        seq = value if isinstance(value, (list, tuple)) else [value]
        casted = [_cast(v, inner) for v in seq]
        return tuple(casted) if origin is tuple else casted

    if origin is dict:
        key_t, val_t = args if len(args) == 2 else (Any, Any)
        if not isinstance(value, dict):
            raise TypeError(f"Expected mapping for {typ}, got {type(value).__name__}")
        return {_cast(k, key_t): _cast(v, val_t) for k, v in value.items()}

    if callable(typ) and not isinstance(typ, str):
        try:
            return typ(value)
        except Exception:
            return value

    return value


def _build_dataclass(cls: type, data: Dict[str, Any]) -> Any:
    """
    Instantiate dataclass 'cls' using 'data' with proper runtime type hints.
    """
    hints = get_type_hints(cls)
    kwargs: Dict[str, Any] = {}

    for field in fields(cls):
        f_type = hints.get(field.name, field.type)
        if field.default is not MISSING:
            default = field.default
        elif getattr(field, "default_factory", MISSING) is not MISSING:  # type: ignore[attr-defined]
            default = field.default_factory()  # type: ignore[misc]
        else:
            default = None

        val = data.get(field.name, default)
        kwargs[field.name] = _cast(val, f_type)

    return cls(**kwargs)

# --------------------------------------------------------------------------- #
#  Env overlays and user-ini discovery
# --------------------------------------------------------------------------- #

def _env_overlays() -> Dict[str, Dict[str, Any]]:
    """
    Read environment variables with the prefix QMTOOL_ and map them to
    sections/keys using a "__" delimiter: QMTOOL_Section__key=value
    """
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
    """
    OS-specific default location for per-user overrides.
    """
    if os.name == "nt":
        appdata = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "QMTool" / "config.ini"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "qmtool" / "config.ini"

# --------------------------------------------------------------------------- #
#  ConfigService
# --------------------------------------------------------------------------- #

class ConfigService:
    """Facade merging layered configuration with type safety and stable path semantics."""

    def __init__(self) -> None:
        self._lock = RLock()
        _ensure_machine_config()
        self._user_ini = _user_config_path()
        self.reload()

    # ------------------------------------------------------------------ #
    def _resolve_base_dir(self, section: str, key: str) -> Path:
        """
        Decide the base directory for relative path resolution for a given (section,key)
        based on the source layer:
          - defaults.ini / code / env / machine -> PROJECT_ROOT
          - user overrides -> directory of the user config.ini
        """
        src = self._sources.get((section, key), {})
        layer = src.get("layer")
        if layer == "user":
            return self._user_ini.parent
        return PROJECT_ROOT

    # ------------------------------------------------------------------ #
    def _prefer_project_file(self, current: Path | None, *, key: str) -> Path | None:
        """
        For Files.* keys: prefer the project-local default file if the current path
        is missing or points outside of the current PROJECT_ROOT.
        """
        if current is None:
            default_str = _DEFAULTS["Files"][key]
            return Path(os.path.expanduser(os.path.expandvars(default_str)))

        try:
            # If 'current' is NOT inside PROJECT_ROOT, use the project-local default
            current.relative_to(PROJECT_ROOT)
            inside = True
        except ValueError:
            inside = False

        default_path = Path(os.path.expanduser(os.path.expandvars(_DEFAULTS["Files"][key])))

        if not current.exists():
            return default_path if default_path.exists() else current

        if not inside and default_path.exists():
            return default_path

        return current

    # ------------------------------------------------------------------ #
    def _normalize_paths(self) -> None:
        """
        Expand env vars and '~', then make all configured paths absolute.
        For Files.* keys we apply a stability fallback to project-local defaults.
        """
        def make_abs(section: str, key: str, p: Path | None) -> Path | None:
            if p is None:
                return None
            expanded = os.path.expandvars(str(p))
            p2 = Path(os.path.expanduser(expanded))
            if not p2.is_absolute():
                base = self._resolve_base_dir(section, key)
                p2 = (base / p2).resolve()
            return p2

        # Database paths
        self.database.qm_tool = make_abs("Database", "qm_tool", self.database.qm_tool)
        self.database.logging = make_abs("Database", "logging", self.database.logging)

        # File paths with project preference fallback
        self.files.modules_json = make_abs("Files", "modules_json", self.files.modules_json)
        self.files.labels_tsv = make_abs("Files", "labels_tsv", self.files.labels_tsv)

        self.files.modules_json = self._prefer_project_file(self.files.modules_json, key="modules_json")
        self.files.labels_tsv = self._prefer_project_file(self.files.labels_tsv, key="labels_tsv")

    # ------------------------------------------------------------------ #
    def reload(self) -> None:
        """
        Rebuild the merged configuration and re-instantiate typed sections.
        Precedence (lowest -> highest):
          0) embedded defaults
          1) defaults.ini (repository)
          2) environment variables (QMTOOL_* overlays)
          3) machine config (core/config/config.ini)
          4) user overrides (~/.config/qmtool/config.ini or %APPDATA%\\QMTool\\config.ini)
        """
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
            self._user_ini = _user_config_path()
            if self._user_ini.exists():
                cp = configparser.ConfigParser()
                cp.read(self._user_ini, encoding="utf-8")
                _apply(merged, _cp_to_dict(cp), "user", str(self._user_ini), sources)

            self._merged = merged
            self._sources = sources

            # Typed sections
            self.database = _build_dataclass(DatabaseConfig, merged.get("Database", {}))
            self.files = _build_dataclass(FilesConfig, merged.get("Files", {}))
            self.general = _build_dataclass(GeneralConfig, merged.get("General", {}))
            self.features = _build_dataclass(FeaturesConfig, merged.get("Features", {}))

            # Normalize & apply fallbacks
            self._normalize_paths()

    # ------------------------------------------------------------------ #
    def get(self, section: str, key: str, *, cast: Callable[[Any], Any] | type = str) -> Any:
        """
        Fetch a raw value from the merged dict and cast it if requested.
        If 'cast' is a type, use the same robust casting logic as for dataclasses.
        If 'cast' is a callable, invoke it directly.
        """
        val = self._merged.get(section, {}).get(key)
        if val is None:
            return None
        if isinstance(cast, type):
            return _cast(val, cast)
        return cast(val)

    def meta_source(self, section: str, key: str) -> Dict[str, str] | None:
        """
        Return provenance information for (section, key): which layer and source file
        provided the effective value, if known.
        """
        return self._sources.get((section, key))


# Global singleton
config_service = ConfigService()
