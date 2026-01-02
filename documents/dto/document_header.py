"""Document header DTO.

TODO: Expand with all required metadata fields.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class DocumentHeader:
    """Immutable document header metadata."""

    doc_id: str
    title: str
    doc_type: str
    status: str
    version_label: str
    owner_id: Optional[str] = None
    updated_at: Optional[datetime] = None
