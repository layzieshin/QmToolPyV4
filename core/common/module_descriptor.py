"""
core/common/module_descriptor.py
================================

DTO + Loader-Hilfen für Module (Meta-JSON basiert).

• from_meta_json(path): liest/validiert Meta und erzeugt Descriptor
• settings_class (optional): vollqualifizierte Settings-Tab-Klasse
• visible_for / settings_for als JSON-Strings in DB
• Lizenz-Felder: license_required, license_tag (optional)
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.models.user import UserRole
from core.logging.logic.logger import logger


@dataclass
class ModuleDescriptor:
    # Persistierte Felder
    id: str
    label: str
    module_path: str
    class_name: str
    version: str
    enabled: int = 1
    is_core: int = 0
    sort_order: int = 999
    visible_for: str = '["Admin","QMB","User"]'
    settings_for: str = '["Admin"]'
    requires_login: int = 1
    permissions: Optional[str] = None
    settings_class: Optional[str] = None
    meta_path: Optional[str] = None
    license_required: int = 0
    license_tag: Optional[str] = None

    # ---------------- Convenience ---------------- #
    @property
    def visible_list(self) -> list[str]:
        try:
            return json.loads(self.visible_for) if self.visible_for else []
        except json.JSONDecodeError:
            return []

    @property
    def settings_list(self) -> list[str]:
        try:
            return json.loads(self.settings_for) if self.settings_for else []
        except json.JSONDecodeError:
            return []

    @property
    def main_class_fq(self) -> str:
        return f"{self.module_path}.{self.class_name}"

    # ---------------- Rollen --------------------- #
    def allowed_in_menu(self, role: str | UserRole | None) -> bool:
        if role is None:
            return True
        r = role.value if isinstance(role, UserRole) else str(role)
        allowed = self.visible_list or ["Admin", "QMB", "User"]
        return "*" in allowed or r in allowed

    def allowed_in_settings(self, role: str | UserRole | None) -> bool:
        if role is None:
            return True
        r = role.value if isinstance(role, UserRole) else str(role)
        allowed = self.settings_list or ["Admin"]
        return "*" in allowed or r in allowed

    # ---------------- Loader --------------------- #
    def safe_load_class(self):
        """Importiert die Hauptklasse; gibt Klasse oder None zurück."""
        try:
            mod = importlib.import_module(self.module_path)
            cls = getattr(mod, self.class_name, None)
            return cls
        except Exception as exc:  # noqa: BLE001
            logger.log("ModuleDescriptor", "ImportError", message=str(exc))
            return None

    # ---------------- Fabriken ------------------- #
    @classmethod
    def from_row(cls, row) -> "ModuleDescriptor":
        return cls(
            id=row["id"],
            label=row["label"],
            module_path=row["module_path"],
            class_name=row["class_name"],
            version=row["version"],
            enabled=row["enabled"],
            is_core=row["is_core"],
            sort_order=row["sort_order"],
            visible_for=row["visible_for"],
            settings_for=row["settings_for"],
            requires_login=row["requires_login"],
            permissions=row["permissions"],
            settings_class=row["settings_class"] if "settings_class" in row.keys() else None,
            meta_path=row["meta_path"] if "meta_path" in row.keys() else None,
            license_required=row["license_required"] if "license_required" in row.keys() else 0,
            license_tag=row["license_tag"] if "license_tag" in row.keys() else None,
        )

    @classmethod
    def from_meta_json(cls, meta_file: Path) -> "ModuleDescriptor":
        data = json.loads(meta_file.read_text(encoding="utf-8"))

        for key in ("id", "label", "version", "main_class"):
            if key not in data or not str(data[key]).strip():
                raise ValueError(f"meta.json: missing required key '{key}'")

        main_cls = str(data["main_class"]).strip()
        if "." not in main_cls:
            raise ValueError("meta.json: 'main_class' must be fully qualified (pkg.mod.Class)")

        module_path = ".".join(main_cls.split(".")[:-1])
        class_name = main_cls.split(".")[-1]

        vis = data.get("visible_for", ["Admin", "QMB", "User"])
        stg = data.get("settings_for", ["Admin"])

        settings_class = data.get("settings_class")
        if settings_class is not None:
            settings_class = str(settings_class).strip()
            if settings_class and "." not in settings_class:
                raise ValueError("meta.json: 'settings_class' must be fully qualified (pkg.mod.Class)")

        lic = data.get("license", {})
        license_required = int(bool(lic.get("required", False)))
        license_tag = str(lic.get("tag")).strip() if lic.get("tag") else None

        return cls(
            id=str(data["id"]).strip(),
            label=str(data["label"]).strip(),
            module_path=module_path,
            class_name=class_name,
            version=str(data["version"]).strip(),
            enabled=int(bool(data.get("enabled", True))),
            is_core=int(bool(data.get("is_core", False))),
            sort_order=int(data.get("sort_order", 999)),
            visible_for=json.dumps(vis),
            settings_for=json.dumps(stg),
            requires_login=int(bool(data.get("requires_login", True))),
            permissions=json.dumps(data.get("permissions")) if data.get("permissions") is not None else None,
            settings_class=settings_class,
            meta_path=str(meta_file.resolve().as_posix()),
            license_required=license_required,
            license_tag=license_tag,
        )
