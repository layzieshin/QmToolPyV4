from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from .ids import WorkflowId, DocumentId
from .workflow_state import WorkflowState
from .workflow_step import WorkflowStep

@dataclass(slots=True)
class WorkflowInstance:
    """
    Runtime instance of a document workflow.
    """
    id: WorkflowId
    document_id: DocumentId
    state: WorkflowState
    created_at: datetime
    updated_at: datetime
    steps: List[WorkflowStep] = field(default_factory=list)
    aborted_reason: Optional[str] = None

    def is_active(self) -> bool:
        return self.state not in (WorkflowState.NONE, WorkflowState.COMPLETED, WorkflowState.ABORTED)
