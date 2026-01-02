"""
Document domain models for the Documents feature.

Keeps the data layer independent from UI and storage details.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List


class DocumentStatus(Enum):
    DRAFT = "DRAFT"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    EFFECTIVE = "EFFECTIVE"
    REVISION = "REVISION"
    OBSOLETE = "OBSOLETE"
    ARCHIVED = "ARCHIVED"

    # Backward-compatible aliases
    IN_REVIEW = "REVIEW"
    APPROVAL = "APPROVED"
    PUBLISHED = "EFFECTIVE"


@dataclass(frozen=True)
class DocumentId:
    value: str
    def __str__(self) -> str:
        return self.value


@dataclass
class DocumentRecord:
    doc_id: DocumentId
    title: str
    doc_type: str
    status: DocumentStatus
    version_major: int
    version_minor: int
    current_file_path: Optional[str] = None

    # New: external code part from file name before "_", e.g. "A02VA001"
    doc_code: Optional[str] = None

    # Optional metadata
    area: Optional[str] = None
    process: Optional[str] = None
    valid_from: Optional[datetime] = None
    next_review: Optional[datetime] = None
    obsoleted_at: Optional[datetime] = None
    created_by: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    change_note: Optional[str] = None
    norm_refs: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    locked_by: Optional[str] = None
    locked_at: Optional[datetime] = None

    @property
    def version_label(self) -> str:
        return f"{self.version_major}.{self.version_minor}"

    @property
    def display_name(self) -> str:
        """
        Preferred display: <doc_code>_<title>  (falls code vorhanden), sonst title.
        """
        return f"{self.doc_code}_{self.title}" if self.doc_code else self.title
