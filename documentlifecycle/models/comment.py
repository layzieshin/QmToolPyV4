from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .ids import CommentId, DocumentId, UserId
from .comment_type import CommentType

@dataclass(slots=True)
class Comment:
    id: CommentId
    document_id: DocumentId
    author_id: UserId
    created_at: datetime
    text: str
    ctype: CommentType = CommentType.GENERAL
    related_version: Optional[str] = None
