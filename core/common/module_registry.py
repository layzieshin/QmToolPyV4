# core/common/module_registry.py
"""
Dynamic module registry helper.

Loads module descriptors from JSON (config/modules.json) and
instantiates the requested view classes.
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Type
from core.config.config_loader import MODULES_JSON_PATH, LABELS_TSV_PATH
REGISTRY_PATH = MODULES_JSON_PATH


@dataclass
class ModuleDescriptor:
    id: str
    label: str
    module: str
    class_name: str
    requires_login: bool

    def load_class(self) -> Type:
        """Dynamically import the GUI class."""
        mod = importlib.import_module(self.module)
        return getattr(mod, self.class_name)


def load_registry() -> Dict[str, ModuleDescriptor]:
    """Return all modules keyed by their id."""
    with open(REGISTRY_PATH, encoding="utf-8") as fh:
        raw: List[dict] = json.load(fh)

    return {
        item["id"]: ModuleDescriptor(
            id=item["id"],
            label=item["label"],
            module=item["module"],
            class_name=item["class"],
            requires_login=item.get("requires_login", False),
        )
        for item in raw
    }
