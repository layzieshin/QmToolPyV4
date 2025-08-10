"""
core/licensing/logic/license_manager.py

High-level check for module licensing.
- meta.json may define:
    "license": { "required": true, "tag": "module-sku" }
- At runtime we check presence of that tag in LicenseRepository.
"""

from __future__ import annotations
from typing import Optional
from core.licensing.logic.license_repository import LicenseRepository
from core.licensing.models.license_status import LicenseStatus


class LicenseManager:
    def __init__(self) -> None:
        self.repo = LicenseRepository()

    def is_module_licensed(self, module_id: str, version: str, license_tag: Optional[str]) -> bool:
        """Simple presence check. Extend with signature/date validation when needed."""
        if not license_tag:
            return False
        return self.repo.has(license_tag)

    def status(self, license_tag: str | None) -> LicenseStatus:
        if not license_tag:
            return LicenseStatus(False, "No license tag")
        if not self.repo.has(license_tag):
            return LicenseStatus(False, "License not found")
        return LicenseStatus(True)


# Global instance
license_manager = LicenseManager()
