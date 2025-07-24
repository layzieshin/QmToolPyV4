"""
core/common/module_descriptor.py
================================

Dataclass für Modul-Metadaten.
Enthält nun eine robuste Rollen-Normalisierung, sodass die
Aufrufer beliebige Enum- oder String-Objekte übergeben können.
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
    id: str
    label: str
    module_path: str
    class_name: str
    enabled: int
    is_core: int
    sort_order: int
    visible_for: str
    settings_for: str
    requires_login: int
    permissions: str | None

    # ------------------------------------------------------------------ #
    #  Interne Helfer                                                    #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _json_to_list(txt: str) -> list[str]:
        try:
            return json.loads(txt)
        except Exception:
            return []

    @staticmethod
    def _role_to_str(role) -> str | None:
        """Konvertiert Enum/String/None in lower-case-String oder None."""
        if role is None:
            return None
        if isinstance(role, Enum):
            # Enum‐Mitglied – erst value (falls str) sonst name
            raw = role.value if isinstance(role.value, str) else role.name
            return str(raw).lower()
        return str(role).lower()

    # ------------------------------------------------------------------ #
    #  Sichtbarkeits-Checks                                              #
    # ------------------------------------------------------------------ #
    def allowed_in_menu(self, role) -> bool:
        allowed = [r.lower() for r in self._json_to_list(self.visible_for)]
        role_str = self._role_to_str(role)
        if role_str is None:
            return False          # vor Login nichts anzeigen
        return "*" in allowed or (role_str in allowed)

    def allowed_in_settings(self, role) -> bool:
        allowed = [r.lower() for r in self._json_to_list(self.settings_for)]
        role_str = self._role_to_str(role)
        if role_str is None:
            return False
        return "*" in allowed or (role_str in allowed)

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
