from __future__ import annotations
from enum import Enum

class DocumentStatus(str, Enum):
    """Business status of a document (domain level, not engine-internals)."""
    DRAFT = "Draft"
    IN_REVIEW = "InReview"
    APPROVED = "Approved"
    PUBLISHED = "Published"
    ARCHIVED = "Archived"
