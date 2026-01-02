"""Assignments DTO for role assignment per document."""

from __future__ import annotations
from dataclasses import dataclass
from typing import List


@dataclass
class Assignments:
    """Role assignments for a document (per-document, not module-wide)."""

    authors: List[str]
    reviewers: List[str]
    approvers: List[str]

    def __post_init__(self):
        """Ensure all fields are lists."""
        self.authors = list(self.authors or [])
        self.reviewers = list(self.reviewers or [])
        self.approvers = list(self.approvers or [])