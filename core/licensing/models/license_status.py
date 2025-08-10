"""
core/licensing/models/license_status.py

Lightweight status object for licensing checks.
"""

from __future__ import annotations
from dataclasses import dataclass

@dataclass
class LicenseStatus:
    ok: bool
    reason: str = ""
