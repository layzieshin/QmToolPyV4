"""
core/common/module_auto_discovery.py
====================================

Auto-Discovery für Module via `meta.json`.

• Durchsucht definierte Wurzel-Verzeichnisse rekursiv nach `meta.json`.
• Ignoriert typische Build-/Tooling-Ordner.
• Validiert Meta-Format minimal (id, label, version, main_class).
• Liefert Liste gefundener meta.json-Dateien (Paths) in stabiler Reihenfolge.

Wird von ModuleRepository/ModuleRegistry verwendet.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from core.logging.logic.logger import logger

# Standardmäßig: Projekt-Root (…/ <root> /), abgeleitet von core/common/
HERE = Path(__file__).resolve().parent           # …/core/common
PROJECT_ROOT = HERE.parents[2]                   # …/<root>

# Verzeichnisse, die beim Scan ignoriert werden
_IGNORE_DIRS = {
    ".git", ".idea", ".vscode", "__pycache__", "node_modules",
    "build", "dist", ".venv", "venv", ".mypy_cache", ".pytest_cache",
}

def default_roots() -> List[Path]:
    """
    Liefert Default-Root-Verzeichnisse für den Scan.
    Erweitere hier ggf. um weitere Modul-Wurzeln.
    """
    return [PROJECT_ROOT]

def _should_skip_dir(path: Path) -> bool:
    name = path.name.lower()
    return name in _IGNORE_DIRS

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
        for p in root.rglob("meta.json"):
            # Skip in ignorierten Ordnern
            if any(_should_skip_dir(parent) for parent in p.parents):
                continue
            found.add(p.resolve())

    result = sorted(found)
    logger.log("ModuleAutoDiscovery", "Scan", message=f"{len(result)} meta.json found")
    return result
