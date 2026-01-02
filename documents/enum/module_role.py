"""Module role enumeration placeholder.

TODO: Keep in sync with RBAC and policy definitions.
"""
from __future__ import annotations

from enum import Enum


class ModuleRole(Enum):
    """Module roles for the documents feature."""

    AUTHOR = "AUTHOR"
    EDITOR = "EDITOR"
    REVIEWER = "REVIEWER"
    APPROVER = "APPROVER"
