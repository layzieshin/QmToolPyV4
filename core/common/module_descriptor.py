"""
core/common/module_descriptor.py
================================

Dataclass + Helper für Modul-Metadaten.
Enthält:
• version   – für Update-/Overwrite-Vergleiche
• robuste Rollen-Normalisierung
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from enum import Enum
from types import ModuleType

from core.logging.logic.logger import logger


@dataclass(slots=True)
class ModuleDescriptor:
    # --- Felder wie in der DB-Tabelle ----------------------------------
    id: str
    label: str
    module_path: str
    class_name: str
    version: str               #  ⇦  NEU
    enabled: int
    is_core: int
    sort_order: int
    visible_for: str
    settings_for: str
    requires_login: int
    permissions: str | None

    # ------------------------------------------------------------------ #
    #  Rollen-Hilfsfunktionen                                            #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _json_to_list(txt: str) -> list[str]:
        try:
            return json.loads(txt)
        except Exception:
            return []

    @staticmethod
    def _role_to_str(role) -> str | None:
        if role is None:
            return None
        if isinstance(role, Enum):
            raw = role.value if isinstance(role.value, str) else role.name
            return str(raw).lower()
        return str(role).lower()

    # ------------------------------------------------------------------ #
    #  Sichtbarkeits-Checks                                              #
    # ------------------------------------------------------------------ #
    def allowed_in_menu(self, role) -> bool:
        allowed = [r.lower() for r in self._json_to_list(self.visible_for)]
        rs = self._role_to_str(role)
        return rs is not None and ("*" in allowed or rs in allowed)

    def allowed_in_settings(self, role) -> bool:
        allowed = [r.lower() for r in self._json_to_list(self.settings_for)]
        rs = self._role_to_str(role)
        return rs is not None and ("*" in allowed or rs in allowed)

    # ------------------------------------------------------------------ #
    #  DB-Mapping                                                        #
    # ------------------------------------------------------------------ #
    @classmethod
    def from_row(cls, row) -> "ModuleDescriptor":
        return cls(**dict(row))

    def to_row(self) -> tuple:
        return (
            self.id,
            self.label,
            self.module_path,
            self.class_name,
            self.version,            #  NEU
            self.enabled,
            self.is_core,
            self.sort_order,
            self.visible_for,
            self.settings_for,
            self.requires_login,
            self.permissions,
        )

    # ------------------------------------------------------------------ #
    #  Sicherer Import                                                   #
    # ------------------------------------------------------------------ #
    def safe_load_class(self):
        try:
            mod: ModuleType = importlib.import_module(self.module_path)
            return getattr(mod, self.class_name)
        except Exception as exc:
            logger.log("ModuleRegistry", "ImportFailed", message=f"{self.id}: {exc}")
            return None
