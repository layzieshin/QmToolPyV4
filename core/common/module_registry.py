"""
core/common/module_registry.py
==============================

Registry-Cache & Class-Loader.

• Startet mit Auto-Discovery (scan meta.json) – einmal pro Prozess.
• Lädt aktivierte Module aus DB, filtert nach Rolle.
"""

from __future__ import annotations

from typing import Dict, Optional

from core.common.module_descriptor import ModuleDescriptor
from core.common.module_repository import ModuleRepository
from core.common.module_auto_discovery import default_roots
from core.logging.logic.logger import logger
from core.models.user import UserRole

_CACHE: Dict[str, ModuleDescriptor] = {}
_LOADED = False


def load_registry(role: Optional[UserRole | str] = None) -> Dict[str, ModuleDescriptor]:
    global _LOADED, _CACHE
    repo = ModuleRepository()

    if not _LOADED:
        # 1) Auto-Discovery: meta.json scannen + registrieren
        repo.discover_and_register(default_roots())
        # 2) DB lesen
        items = repo.all_modules(enabled_only=True)
        _CACHE = {d.id: d for d in items}
        _LOADED = True
        logger.log("ModuleRegistry", "CacheBuilt", message=f"{len(_CACHE)} entries")

    if role is None:
        return dict(_CACHE)

    return {mid: d for mid, d in _CACHE.items() if d.allowed_in_menu(role)}


def invalidate_registry_cache() -> None:
    global _LOADED, _CACHE
    _LOADED = False
    _CACHE.clear()
    logger.log("ModuleRegistry", "CacheInvalidated")
