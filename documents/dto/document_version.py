"""Document version DTO.

TODO: Model immutable version metadata and links.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class DocumentVersion:
    """Immutable document version descriptor."""

    version_label: str
    major: int
    minor: int
    created_at: Optional[datetime] = None
    reason: Optional[str] = None
