from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass(frozen=True)
class ReviewComment:
    """
    Model for a single Word review comment (Überarbeiten/Randkommentar).
    """
    comment_id: int
    author: Optional[str]
    date: Optional[datetime]
    text: str
