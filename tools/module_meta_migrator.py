"""
tools/module_meta_migrator.py

Create 'meta.json' for existing feature modules automatically.

Heuristics:
- A "module" is a top-level package (directory with __init__.py) that is not 'core' or 'framework'.
- main_class: first class in package.gui.*_view.py that subclasses tk/ttk.Frame
- settings_class: first class in package.gui.*settings*view.py that subclasses tk/ttk.Frame
- meta.json is generated if it does NOT exist yet.
- You review generated meta.json and adjust (label/version/sort orders/roles).

Run:
  python tools/module_meta_migrator.py
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]

IGNORE_PKGS = {"core", "framework", ".venv", "venv", "build", "dist", "__pycache__"}


def is_pkg(dirpath: Path) -> bool:
    return (dirpath / "__init__.py").exists()


def find_first_frame_class(py_file: Path) -> Optional[Tuple[str, str]]:
    """
    Returns (module_path, class_name) if a tk/ttk.Frame subclass is found.
    Parsing via AST (no import execution).
    """
    try:
        src = py_file.read_text(encoding="utf-8")
    except Exception:
        return None

    try:
        tree = ast.parse(src, filename=str(py_file))
    except SyntaxError:
        return None

    class_names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # base names like Frame, ttk.Frame, tk.Frame
            base_names = []
            for b in node.bases:
                if isinstance(b, ast.Name):
                    base_names.append(b.id)
                elif isinstance(b, ast.Attribute):
                    # e.g. ttk.Frame or tk.Frame
                    parts = []
                    cur = b
                    while isinstance(cur, ast.Attribute):
                        parts.append(cur.attr)
                        cur = cur.value
                    if isinstance(cur, ast.Name):
                        parts.append(cur.id)
                    base_names.append(".".join(reversed(parts)))
            if any(n.endswith("Frame") for n in base_names):
                class_names.append(node.name)

    if not class_names:
        return None

    # derive module path like: packagename.gui.filename(without .py)
    # locate package root by looking up for __init__.py files
    rel = py_file.relative_to(PROJECT_ROOT)
    parts = list(rel.parts)
    parts[-1] = parts[-1].removesuffix(".py")
    module_path = ".".join(parts)
    return module_path, class_names[0]


def suggest_meta_for_package(pkg_dir: Path) -> Optional[dict]:
    meta_path = pkg_dir / "meta.json"
    if meta_path.exists():
        return None  # keep existing

    gui_dir = pkg_dir / "gui"
    if not gui_dir.exists():
        return None

    # find view
    main_candidate: Optional[Tuple[str, str]] = None
    for py in gui_dir.glob("*view.py"):
        res = find_first_frame_class(py)
        if res:
            module_path, cls_name = res
            if "settings" not in py.name.lower():
                main_candidate = (module_path, cls_name)
                break

    if not main_candidate:
        return None

    # find settings view (optional)
    settings_candidate: Optional[Tuple[str, str]] = None
    for py in gui_dir.glob("*settings*view.py"):
        res = find_first_frame_class(py)
        if res:
            settings_candidate = res
            break

    pkg_id = pkg_dir.name.lower()
    label = pkg_dir.name.capitalize().replace("_", " ")

    meta = {
        "id": pkg_id,
        "label": label,
        "version": "0.0.1",
        "main_class": f"{main_candidate[0]}.{main_candidate[1]}",
        "visible_for": ["Admin", "QMB", "User"],
        "settings_for": ["Admin"],
        "is_core": False,
        "sort_order": 500,
        "requires_login": True
    }
    if settings_candidate:
        meta["settings_class"] = f"{settings_candidate[0]}.{settings_candidate[1]}"

    return meta


def main() -> int:
    created = 0
    for child in PROJECT_ROOT.iterdir():
        if not child.is_dir():
            continue
        if child.name in IGNORE_PKGS:
            continue
        if not is_pkg(child):
            continue
        # e.g. your feature packages like 'clockwork', 'documents', ...
        meta = suggest_meta_for_package(child)
        if not meta:
            continue
        out = child / "meta.json"
        out.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[GEN] {out}")
        created += 1

    print(f"\nDone. Generated {created} meta.json file(s). Please review them.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
