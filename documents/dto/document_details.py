"""DocumentDetails DTO for detail view rendering."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class DocumentDetails:
    """
    Complete detail information for UI rendering.

    Combines:
    - Document metadata
    - DOCX core properties
    - Current actors (effective for workflow step)
    - Comments (DOCX + PDF)
    """

    # Core fields
    doc_id: str
    title: str
    doc_type: str
    status: str
    version_label: str
    current_file_path: Optional[str] = None

    # Metadata (from DOCX core properties)
    description: Optional[str] = None
    documenttype: Optional[str] = None
    actual_filetype: Optional[str] = None
    valid_by_date: Optional[str] = None
    last_modified: Optional[str] = None

    # Current actors (effective for current workflow step)
    editor: Optional[str] = None
    reviewer: Optional[str] = None
    publisher: Optional[str] = None
    editor_dt: Optional[str] = None
    reviewer_dt: Optional[str] = None
    publisher_dt: Optional[str] = None

    # Comments
    docx_comments: List[Dict[str, Any]] = field(default_factory=list)
    pdf_comments: List[Dict[str, Any]] = field(default_factory=list)