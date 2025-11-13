from __future__ import annotations
from enum import Enum

class CommentType(str, Enum):
    """Comment semantics for later filtering/reporting."""
    GENERAL = "General"
    CHANGE_REQUEST = "ChangeRequest"
    NOTE = "Note"
    ISSUE = "Issue"
