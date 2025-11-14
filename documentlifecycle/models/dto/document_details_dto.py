from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass(slots=True)
class DocumentDetailsDTO:
    """
    Everything the Details tab needs – mapped & formatted.
    """
    id: int
    title: str
    description: str
    status: str
    doc_type: str
    version: str               # "1.3"
    revision: int
    path: str

    # Roles (display strings, not IDs)
    editor: Optional[str]
    reviewer: Optional[str]
    publisher: Optional[str]

    # Dates (already formatted for UI)
    edited_at: Optional[str]
    reviewed_at: Optional[str]
    published_at: Optional[str]
    valid_from: Optional[str]
    valid_until: Optional[str]
    archived_at: Optional[str]
