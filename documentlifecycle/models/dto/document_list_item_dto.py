from __future__ import annotations
from dataclasses import dataclass

@dataclass(slots=True)
class DocumentListItemDTO:
    """
    Lightweight row for the left list.
    Keep strings preformatted for the UI.
    """
    id: int
    title: str
    status: str
    doc_type: str
    version: str           # e.g., "1.3 (rev 7)"
    updated: str           # e.g., "2025-09-27"
