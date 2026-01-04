"""
core/common/module_auto_discovery.py
====================================

Module auto-discovery via `meta.json`.

IMPORTANT ARCHITECTURE RULE:
- ConfigLoader is the SINGLE source of truth for project root and config paths.
- This module must not implement its own root strategy (no Path(__file__).parents hacks,
  no marker files, no cwd assumptions).

Behavior:
- Recursively searches given roots for `meta.json`.
- Ignores typical tooling/build directories.
- Returns a deterministically sorted list of found meta.json files.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, List

from core.config.config_loader import PROJECT_ROOT_PATH_T
from core.qm_logging.logic.logger import logger

_IGNORE_DIRS = {
    ".git", ".idea", ".vscode", "__pycache__", "node_modules",
    "build", "dist", ".venv", "venv", ".mypy_cache", ".pytest_cache",
}


def default_roots() -> List[Path]:
    """
    Default root directories for module scanning.

    - Dev run: PROJECT_ROOT_PATH_T (ConfigLoader)
    - Frozen (PyInstaller onedir): <exe_dir>/_internal
    """
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        internal = exe_dir / "_internal"
        return [internal]

    return [PROJECT_ROOT_PATH_T]


def _in_ignored_dir(p: Path) -> bool:
    """
    Returns True if path is located inside a directory that we want to ignore.
    """
    for parent in p.parents:
        if parent.name in _IGNORE_DIRS:
            return True
    return False


def discover_meta_files(roots: Iterable[Path] | None = None) -> List[Path]:
    """
    Recursively scan for `meta.json` under the given roots.

    Returns:
        Deterministically sorted list of resolved meta.json Paths.
    """
    scan_roots = list(roots) if roots else default_roots()
    found: set[Path] = set()

    # Single source of truth root reference (for sanity checks)
    if getattr(sys, "frozen", False):
        project_root = (Path(sys.executable).resolve().parent / "_internal").resolve()
    else:
        project_root = PROJECT_ROOT_PATH_T.resolve()

    for root in scan_roots:
        if not root:
            continue

        root = Path(root).resolve()

        if not root.exists():
            logger.log("ModuleAutoDiscovery", "RootMissing", message=str(root))
            continue

        for meta in root.rglob("meta.json"):
            try:
                if _in_ignored_dir(meta):
                    continue

                meta_resolved = meta.resolve()

                # Ensure the discovered file is within the active project root
                if not meta_resolved.is_relative_to(project_root):
                    continue

                found.add(meta_resolved)

            except Exception as exc:  # noqa: BLE001
                logger.log("ModuleAutoDiscovery", "ScanError", message=f"{meta}: {exc}")

    result = sorted(found)
    logger.log("ModuleAutoDiscovery", "Scan", message=f"{len(result)} meta.json found")
    return result
