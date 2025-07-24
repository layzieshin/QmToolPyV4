"""
core/common/module_registry.py
==============================

Caching-Loader für aktive Module.

• sortiert jetzt nach *sort_order*
"""

from __future__ import annotations

from typing import Dict

from core.common.module_repository import ModuleRepository
from core.common.module_descriptor import ModuleDescriptor
from core.logging.logic.logger import logger

_CACHE: Dict[str, ModuleDescriptor] | None = None


def load_registry(role: str | None = None) -> Dict[str, ModuleDescriptor]:
    global _CACHE
    if _CACHE is None:
        repo = ModuleRepository()
        # nach sort_order sortieren
        _CACHE = {d.id: d for d in sorted(repo.enabled_modules(), key=lambda d: d.sort_order)}

    return {mid: desc for mid, desc in _CACHE.items() if desc.allowed_in_menu(role)}


def invalidate_registry_cache() -> None:
    global _CACHE
    _CACHE = None
    logger.log("ModuleRegistry", "CacheInvalidated")
