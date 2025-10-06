from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass(frozen=True)
class CoreProperties:
    """
    Strongly-typed container for Word Core Properties (docProps/core.xml).
    All fields are optional because many documents omit some properties.
    """
    title: Optional[str] = None
    subject: Optional[str] = None
    author: Optional[str] = None
    last_modified_by: Optional[str] = None
    created: Optional[datetime] = None
    modified: Optional[datetime] = None
    category: Optional[str] = None
    comments: Optional[str] = None
    keywords: Optional[str] = None
    version: Optional[str] = None
    revision: Optional[int] = None
    last_printed: Optional[datetime] = None
    identifier: Optional[str] = None
    language: Optional[str] = None
    content_status: Optional[str] = None
