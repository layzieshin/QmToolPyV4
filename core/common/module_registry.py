"""
Module Registry (static, no DB)
===============================

• Builds the registry cache once from the static Module Catalog (modules.json + meta.json).
• Filters by role & licensing.
• Essentials (e.g. 'settings') are never blocked.

Frozen safety:
- In PyInstaller onedir builds, dynamic discovery may fail depending on where modules.json/cwd points to.
- If the catalog is empty in a frozen run, we fall back to scanning meta.json directly under <exe_dir>/_internal.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, Optional

from core.common.module_descriptor import ModuleDescriptor
from core.common.module_catalog import get_catalog, invalidate_catalog
from core.licensing.logic.license_manager import license_manager
from core.qm_logging.logic.logger import logger
from core.models.user import UserRole

_CACHE: Dict[str, ModuleDescriptor] = {}
_LOADED = False

# Modules that must always be visible (keep intentionally small)
_ESSENTIAL_MODULE_IDS = {"settings"}


def _frozen_internal_root() -> Optional[Path]:
    if not getattr(sys, "frozen", False):
        return None
    exe_dir = Path(sys.executable).resolve().parent
    internal = exe_dir / "_internal"
    return internal if internal.exists() else None


def _scan_meta_json_direct(roots: list[Path]) -> Dict[str, ModuleDescriptor]:
    """
    Direct filesystem scan for meta.json (fallback path).
    Returns descriptors keyed by id. Later duplicates keep first.
    """
    found: Dict[str, ModuleDescriptor] = {}
    for root in roots:
        try:
            if not root.exists():
                continue
            for meta in root.rglob("meta.json"):
                try:
                    d = ModuleDescriptor.from_meta_json(meta)
                    if d.id not in found:
                        found[d.id] = d
                except Exception as exc:  # noqa: BLE001
                    logger.log("ModuleRegistry", "MetaParseError", message=f"{meta}: {exc}")
        except Exception as exc:  # noqa: BLE001
            logger.log("ModuleRegistry", "MetaScanError", message=f"{root}: {exc}")
    return found


def load_registry(role: Optional[UserRole | str] = None) -> Dict[str, ModuleDescriptor]:
    """
    Build (once) and return the module registry, optionally filtered by role.

    Behavior:
    - enabled==0 modules are ignored.
    - If role is None (pre-login), only essentials are returned.
    - If frozen and catalog is empty, fallback to scanning meta.json directly under _internal.
    """
    global _LOADED, _CACHE

    if not _LOADED:
        catalog_values = list(get_catalog().values())

        # FROZEN FALLBACK: if catalog is empty, scan meta.json directly
        if not catalog_values and getattr(sys, "frozen", False):
            internal = _frozen_internal_root()
            if internal is not None:
                logger.log("ModuleRegistry", "FrozenFallback", message=str(internal))
                catalog_values = list(_scan_meta_json_direct([internal]).values())

        # Licensing + enabled filter; essentials always kept
        filtered: Dict[str, ModuleDescriptor] = {}
        for d in catalog_values:
            # Ignore explicitly disabled modules
            if not getattr(d, "enabled", 1):
                logger.log("ModuleRegistry", "ModuleDisabled", message=d.id)
                continue

            if d.id in _ESSENTIAL_MODULE_IDS:
                filtered[d.id] = d
                continue

            if getattr(d, "license_required", 0):
                ok = license_manager.is_module_licensed(d.id, d.version, d.license_tag)
                if not ok:
                    logger.log("ModuleRegistry", "LicenseBlocked", message=d.id)
                    continue

            filtered[d.id] = d

        _CACHE = filtered
        _LOADED = True
        logger.log("ModuleRegistry", "CacheBuilt", message=f"{len(_CACHE)} entries (static)")

    # Pre-login: only essentials
    if role is None:
        return {mid: d for mid, d in _CACHE.items() if mid in _ESSENTIAL_MODULE_IDS}

    # Normal role filter
    result = {mid: d for mid, d in _CACHE.items() if d.allowed_in_menu(role)}
    logger.log("ModuleRegistry", "RoleFilter", message=f"role={role} -> {len(result)} entries")
    return result


def invalidate_registry_cache() -> None:
    """Drop the in-memory cache so the next call rebuilds it."""
    global _LOADED, _CACHE
    _LOADED = False
    _CACHE.clear()
    invalidate_catalog()
    logger.log("ModuleRegistry", "CacheInvalidated")
