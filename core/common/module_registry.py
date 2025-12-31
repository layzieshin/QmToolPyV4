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
from core.common.module_catalog import get_catalog, invalidate_catalog
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

    Änderungen gegenüber ursprünglicher Implementierung:
    - Module mit enabled == 0 werden beim Aufbau des Caches ignoriert.
    - Wenn role is None (VOR dem Login), werden nur noch die
      als essentiell definierten Module (_ESSENTIAL_MODULE_IDS) zurückgegeben.
      Damit werden vor dem Login nicht mehr alle entdeckten Module
      in der Navigation angezeigt (verringert Startzeit und Verwirrung).
    """
    global _LOADED, _CACHE

    if not _LOADED:
        all_items = get_catalog().values()

        # Lizenz-Filter + enabled-Filter: nur lizenzierte UND aktivierte Module,
        # Essentials werden immer beibehalten.
        filtered: Dict[str, ModuleDescriptor] = {}
        for d in all_items:
            # Ignoriere explizit deaktivierte Module
            if not getattr(d, "enabled", 1):
                logger.log("ModuleRegistry", "ModuleDisabled", message=d.id)
                continue

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

    # Wenn role None (vor Login), nur Essentials zurückgeben.
    if role is None:
        return {mid: d for mid, d in _CACHE.items() if mid in _ESSENTIAL_MODULE_IDS}

    return {mid: d for mid, d in _CACHE.items() if d.allowed_in_menu(role)}

def invalidate_registry_cache() -> None:
    """Drop the in-memory cache so the next call rebuilds it."""
    global _LOADED, _CACHE
    _LOADED = False
    _CACHE.clear()
    invalidate_catalog()
    logger.log("ModuleRegistry", "CacheInvalidated")
