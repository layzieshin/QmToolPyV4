from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class ExtendedProperties:
    """
    Extended/App properties from docProps/app.xml (application statistics etc.).
    """
    application: Optional[str] = None
    app_version: Optional[str] = None
    company: Optional[str] = None
    manager: Optional[str] = None  # often absent; appears if author filled it
    total_time_minutes: Optional[int] = None
    pages: Optional[int] = None
    words: Optional[int] = None
    characters: Optional[int] = None
    characters_with_spaces: Optional[int] = None
    lines: Optional[int] = None
    paragraphs: Optional[int] = None
    doc_security: Optional[int] = None
    hyperlinks_changed: Optional[bool] = None
    links_up_to_date: Optional[bool] = None
    shared_doc: Optional[bool] = None
