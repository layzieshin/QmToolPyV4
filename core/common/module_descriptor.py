"""
core/common/module_descriptor.py
================================

DTO + Loader helpers for modules (meta.json based).

• from_meta_json(path): reads/validates meta and creates descriptor
• settings_class (optional): fully qualified Settings-Tab class
• visible_for / settings_for stored as JSON strings
• License fields: license_required, license_tag (optional)
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.models.user import UserRole
from core.qm_logging.logic.logger import logger


@dataclass
class ModuleDescriptor:
    # Persisted fields
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

    # ---------------- Roles --------------------- #
    @staticmethod
    def _norm_role(role: str | UserRole | None) -> str | None:
        """Normalize role to a comparable string (case-insensitive)."""
        if role is None:
            return None
        r = role.value if isinstance(role, UserRole) else str(role)
        r = r.strip()
        return r.lower() if r else None

    @staticmethod
    def _norm_allowed(values: list[str] | None, fallback: list[str]) -> set[str]:
        """Normalize allowed role list (case-insensitive)."""
        raw = values if values else fallback
        return {str(x).strip().lower() for x in raw if str(x).strip()}

    def allowed_in_menu(self, role: str | UserRole | None) -> bool:
        """
        Return True if module should appear in the menu for the given role.
        Visible list supports '*' wildcard.
        """
        r = self._norm_role(role)
        if r is None:
            return True

        allowed = self.visible_list
        allowed_norm = self._norm_allowed(allowed, ["Admin", "QMB", "User"])
        return "*" in allowed_norm or r in allowed_norm

    def allowed_in_settings(self, role: str | UserRole | None) -> bool:
        """
        Return True if module settings are accessible for the given role.
        Settings list supports '*' wildcard.
        """
        r = self._norm_role(role)
        if r is None:
            return True

        allowed = self.settings_list
        allowed_norm = self._norm_allowed(allowed, ["Admin"])
        return "*" in allowed_norm or r in allowed_norm

    # ---------------- Loader --------------------- #
    def safe_load_class(self):
        """Import the main class; returns class or None.

        Improvements:
        - Full traceback is logged on failure.
        - Missing class in an importable module is logged.
        - The method is crash-safe (returns None on error).
        """
        try:
            mod = importlib.import_module(self.module_path)
            cls = getattr(mod, self.class_name, None)
            if cls is None:
                logger.log(
                    "ModuleDescriptor",
                    "ImportError",
                    message=f"Module imported ({self.module_path}) but class '{self.class_name}' not found",
                )
            return cls
        except Exception as exc:  # noqa: BLE001
            import traceback

            tb = traceback.format_exc()
            logger.log(
                "ModuleDescriptor",
                "ImportError",
                message=f"Importing {self.module_path}.{self.class_name} failed: {exc}\n{tb}",
            )
            return None

    # ---------------- Factories ------------------- #
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
