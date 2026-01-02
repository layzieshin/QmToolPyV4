"""Assignments DTO for role assignment per document."""

from __future__ import annotations
from dataclasses import dataclass
from typing import List


@dataclass
class Assignments:
    """
    Role assignments for a document (per-document, not module-wide).

    Used for workflow routing - defines who is responsible for each step.
    """

    authors: List[str]
    """List of user IDs assigned as authors/editors"""

    reviewers: List[str]
    """List of user IDs assigned as reviewers"""

    approvers: List[str]
    """List of user IDs assigned as approvers/publishers"""

    def __post_init__(self):
        """Ensure all fields are lists."""
        self.authors = list(self.authors or [])
        self.reviewers = list(self.reviewers or [])
        self.approvers = list(self.approvers or [])

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "AUTHOR": self.authors,
            "REVIEWER": self.reviewers,
            "APPROVER": self.approvers,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Assignments":
        """Create from dictionary."""
        return cls(
            authors=data.get("AUTHOR", []),
            reviewers=data.get("REVIEWER", []),
            approvers=data.get("APPROVER", []),
        )