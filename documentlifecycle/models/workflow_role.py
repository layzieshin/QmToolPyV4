from __future__ import annotations
from enum import Enum

class WorkflowRole(str, Enum):
    """Per-document workflow roles (who does what for THIS document)."""
    AUTHOR = "Author"
    REVIEWER = "Reviewer"
    APPROVER = "Approver"
