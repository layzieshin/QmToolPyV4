from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .workflow_role import WorkflowRole

@dataclass(slots=True)
class WorkflowStep:
    """
    Describes one step in the workflow, typically tied to a WorkflowRole.
    Example: Authoring -> Reviewing -> Approval.
    """
    name: str                   # e.g., "Authoring", "Review"
    role: WorkflowRole          # who is responsible in this step?
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def is_completed(self) -> bool:
        return self.completed_at is not None
