from __future__ import annotations
from dataclasses import dataclass

@dataclass(slots=True)
class CommentDTO:
    """Flat row for the comments grid."""
    author: str
    date: str
    text: str
