"""Document type specification DTO.

TODO: Capture policy-driven type requirements.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class TypeSpec:
    """Immutable definition of a document type."""

    code: str
    requires_review: bool
    requires_approval: bool
    allow_self_approval: bool
    required_signatures: List[str]
