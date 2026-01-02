"""Document status enumeration.

TODO: Align with policy-driven workflow definitions.
"""
from __future__ import annotations

from enum import Enum


class DocumentStatus(Enum):
    """Canonical document lifecycle statuses."""

    DRAFT = "DRAFT"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    EFFECTIVE = "EFFECTIVE"
    REVISION = "REVISION"
    OBSOLETE = "OBSOLETE"
    ARCHIVED = "ARCHIVED"
