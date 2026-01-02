"""documents/enum/module_role.py
===========================

Module roles for the documents feature.

These roles are *document-scoped* (assigned per document), not global system roles.
"""
from __future__ import annotations

from enum import Enum


class ModuleRole(str, Enum):
    """Document-scoped module roles."""

    AUTHOR = "AUTHOR"
    EDITOR = "EDITOR"
    REVIEWER = "REVIEWER"
    APPROVER = "FREIGEBER"
