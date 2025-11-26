"""
core/common/module_auto_discovery.py
====================================

Auto-Discovery für Module via `meta.json`.

• Durchsucht definierte Wurzel-Verzeichnisse rekursiv nach `meta.json`.
• Ignoriert typische Build-/Tooling-Ordner.
• Gibt eine deterministisch sortierte Liste gefundener Dateien zurück.

Performance optimizations:
• Uses set lookup for ignored directory names (O(1) instead of O(n))
• Checks path parts directly instead of iterating all parents
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from core.logging.logic.logger import logger

HERE = Path(__file__).resolve().parent           # .../core/common
PROJECT_ROOT = HERE.parents[2]                   # .../<root>

_IGNORE_DIRS = frozenset({
    ".git", ".idea", ".vscode", "__pycache__", "node_modules",
    "build", "dist", ".venv", "venv", ".mypy_cache", ".pytest_cache",
})

def default_roots() -> List[Path]:
    """
    Liefert Default-Root-Verzeichnisse für den Scan.
    Erweitere hier ggf. um weitere Modul-Wurzeln (z.B. aus ConfigLoader).
    """
    return [PROJECT_ROOT]

def _in_ignored_dir(p: Path) -> bool:
    """
    Check if any component of the path is in the ignored directories set.
    Uses generator with any() for efficient short-circuit evaluation.
    """
    return any(part in _IGNORE_DIRS for part in p.parts)

def discover_meta_files(roots: Iterable[Path] | None = None) -> List[Path]:
    """
    Rekursiver Scan nach `meta.json` unterhalb der angegebenen Roots.
    Rückgabe sortiert (deterministisch).
    """
    roots = list(roots) if roots else default_roots()
    found: set[Path] = set()

    for root in roots:
        if not root.exists():
            continue
        for meta in root.rglob("meta.json"):
            if _in_ignored_dir(meta):
                continue
            found.add(meta.resolve())

    result = sorted(found)
    logger.log("ModuleAutoDiscovery", "Scan", message=f"{len(result)} meta.json found")
    return result
