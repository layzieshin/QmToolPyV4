from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from .ids import DocumentId, UserId
from .workflow_role import WorkflowRole

@dataclass(slots=True)
class RoleAssignment:
    """
    Assigns a workflow role for a specific document to a specific user.
    This is separate from SystemRole (global) and lives at document scope.
    """
    document_id: DocumentId
    user_id: UserId
    role: WorkflowRole
    note: Optional[str] = None
