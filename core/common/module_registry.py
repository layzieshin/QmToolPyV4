# core/common/module_registry.py
"""
Module Registry (static, no DB)
===============================

• Baut den Registry-Cache einmalig aus dem static Module Catalog (modules.json + meta.json).
• Filtert nach Rolle & Lizenz.
• Essentials (z. B. 'settings') werden nie geblockt.
"""

from __future__ import annotations

from typing import Dict, Optional

from core.common.module_descriptor import ModuleDescriptor
from core.common.module_catalog import get_catalog
from core.licensing.logic.license_manager import license_manager
from core.logging.logic.logger import logger
from core.models.user import UserRole

_CACHE: Dict[str, ModuleDescriptor] = {}
_LOADED = False

# Module, die immer sichtbar sein sollen (z. B. um die App konfigurieren zu können)
_ESSENTIAL_MODULE_IDS = {"settings"}  # bewusst klein halten


def load_registry(role: Optional[UserRole | str] = None) -> Dict[str, ModuleDescriptor]:
    """
    Build (once) and return the module registry, optionally filtered by role.

    Behavior:
    - Source: static module catalog (no DB).
    - Lizenzfilter bleibt erhalten; Essentials (z. B. 'settings') werden nie geblockt.
    """
    global _LOADED, _CACHE

    if not _LOADED:
        all_items = get_catalog().values()

        # Lizenz-Filter: nur lizenzierte Module, Essentials immer erlauben
        filtered: Dict[str, ModuleDescriptor] = {}
        for d in all_items:
            if d.id in _ESSENTIAL_MODULE_IDS:
                filtered[d.id] = d
                continue

            if d.license_required:
                ok = license_manager.is_module_licensed(d.id, d.version, d.license_tag)
                if not ok:
                    logger.log("ModuleRegistry", "LicenseBlocked", message=d.id)
                    continue

            filtered[d.id] = d

        _CACHE = filtered
        _LOADED = True
        logger.log("ModuleRegistry", "CacheBuilt", message=f"{len(_CACHE)} entries (static)")

    if role is None:
        return dict(_CACHE)

    return {mid: d for mid, d in _CACHE.items() if d.allowed_in_menu(role)}


def invalidate_registry_cache() -> None:
    """Drop the in-memory cache so the next call rebuilds it."""
    global _LOADED, _CACHE
    _LOADED = False
    _CACHE.clear()
    logger.log("ModuleRegistry", "CacheInvalidated")
