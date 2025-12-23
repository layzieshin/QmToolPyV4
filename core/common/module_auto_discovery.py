"""
core/common/module_auto_discovery.py
====================================

Auto-Discovery für Module via `meta.json`.

• Durchsucht definierte Wurzel-Verzeichnisse rekursiv nach `meta.json`.
• Ignoriert typische Build-/Tooling-Ordner.
• Gibt eine deterministisch sortierte Liste gefundener Dateien zurück.

Performance optimizations:
• Uses frozenset for ignored directory names (immutable, O(1) lookups)
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
    Check if the path is inside any ignored directory.
    Uses frozenset for O(1) lookups while maintaining the original
    parent-directory-only semantic (not checking the filename itself).
    """
    # Only check parent directories (not the file itself)
    # This maintains the original behavior of checking if the file is
    # *inside* an ignored directory, not if the file *is* an ignored name
    for parent in p.parents:
        if parent.name in _IGNORE_DIRS:
            return True
    return False

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
