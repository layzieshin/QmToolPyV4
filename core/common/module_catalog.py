"""
Static Module Catalog (no DB persistence)
=========================================
Loads modules once from:
  1) core/config/modules.json   (primary; curated)
  2) meta.json auto-discovery   (optional add-on)

Only module *settings* live in SQLite (via SettingsManager); the module list
itself does not.

Thread-safe, cached. Use:
    from core.common.module_catalog import get_catalog, invalidate_catalog
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from threading import RLock
from typing import Dict

from core.common.module_descriptor import ModuleDescriptor
from core.common.module_auto_discovery import discover_meta_files, default_roots
from core.config.config_loader import MODULES_JSON_PATH
from core.qm_logging.logic.logger import logger

# In-memory cache
_CATALOG: Dict[str, ModuleDescriptor] = {}
_LOADED = False
_LOCK = RLock()


def _from_modules_json_entry(entry: dict) -> ModuleDescriptor:
    """
    Map minimal modules.json entry → ModuleDescriptor with sane defaults.
    Expected keys in modules.json: id, label, module, class, (optional) requires_login
    """
    module_path = str(entry["module"]).strip()
    class_name = str(entry["class"]).strip()
    return ModuleDescriptor(
        id=str(entry["id"]).strip(),
        label=str(entry["label"]).strip(),
        module_path=module_path,
        class_name=class_name,
        version=str(entry.get("version", "0.0.0")).strip(),
        enabled=1 if entry.get("enabled", True) else 0,
        is_core=1 if entry.get("is_core", False) else 0,
        sort_order=int(entry.get("sort_order", 999)),
        visible_for=json.dumps(entry.get("visible_for", ["Admin", "QMB", "User"])),
        settings_for=json.dumps(entry.get("settings_for", ["Admin"])),
        requires_login=1 if entry.get("requires_login", True) else 0,
        permissions=json.dumps(entry.get("permissions")) if entry.get("permissions") is not None else None,
        settings_class=str(entry["settings_class"]).strip() if entry.get("settings_class") else None,
        meta_path=None,
        license_required=1 if (entry.get("license") or {}).get("required") else 0,
        license_tag=str((entry.get("license") or {}).get("tag")).strip() if (entry.get("license") or {}).get("tag") else None,
    )


def _load_modules_json() -> Dict[str, ModuleDescriptor]:
    items: Dict[str, ModuleDescriptor] = {}
    path: Path = MODULES_JSON_PATH
    if not path.exists():
        logger.log("ModuleCatalog", "ModulesJsonMissing", message=str(path))
        return items

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("modules.json must be a list")
        for raw in data:
            try:
                d = _from_modules_json_entry(raw)
                items[d.id] = d
            except Exception as exc:  # noqa: BLE001
                logger.log("ModuleCatalog", "ModulesJsonEntryError", message=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.log("ModuleCatalog", "ModulesJsonReadError", message=str(exc))
    else:
        logger.log("ModuleCatalog", "ModulesJsonLoaded", message=f"{len(items)} entries")

    return items


def _augment_with_auto_discovery(items: Dict[str, ModuleDescriptor]) -> None:
    """
    Optionally augment catalog with meta.json-discovered modules (no overwrite).

    Rule:
    - Non-frozen run: skip auto-discovery if modules.json has entries
    - Frozen run: ALWAYS allow auto-discovery (distribution must be self-contained)
    """
    try:
        if items and not getattr(sys, "frozen", False):
            logger.log(
                "ModuleCatalog",
                "AutoDiscoverySkip",
                message="modules.json present, skipping auto-discovery (non-frozen run)",
            )
            return

        metas = discover_meta_files(default_roots())
        count = 0
        for meta in metas:
            try:
                desc = ModuleDescriptor.from_meta_json(meta)
                if desc.id not in items:
                    items[desc.id] = desc
                    count += 1
            except Exception as exc:  # noqa: BLE001
                logger.log("ModuleCatalog", "MetaParseError", message=f"{meta}: {exc}")

        if count:
            logger.log("ModuleCatalog", "AutoDiscoveryAugmented", message=f"+{count} entries")

    except Exception as exc:  # noqa: BLE001
        logger.log("ModuleCatalog", "AutoDiscoveryFailed", message=str(exc))


def _build_catalog() -> Dict[str, ModuleDescriptor]:
    items = _load_modules_json()
    _augment_with_auto_discovery(items)
    return items


def get_catalog() -> Dict[str, ModuleDescriptor]:
    """Return cached catalog; build once if necessary."""
    global _LOADED, _CATALOG
    if _LOADED:
        return dict(_CATALOG)
    with _LOCK:
        if not _LOADED:
            _CATALOG = _build_catalog()
            _LOADED = True
            logger.log("ModuleCatalog", "CatalogBuilt", message=f"{len(_CATALOG)} entries")
        return dict(_CATALOG)


def invalidate_catalog() -> None:
    """Drop the in-memory catalog to force rebuild on next get_catalog()."""
    global _LOADED, _CATALOG
    with _LOCK:
        _CATALOG.clear()
        _LOADED = False
        logger.log("ModuleCatalog", "CatalogInvalidated")
