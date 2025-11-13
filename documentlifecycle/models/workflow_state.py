from __future__ import annotations
from enum import Enum

class WorkflowState(str, Enum):
    """High-level state of a workflow instance for a document."""
    NONE = "None"                # no active workflow
    EDITING = "Editing"          # authoring phase
    UNDER_REVIEW = "UnderReview" # reviewers working
    APPROVAL = "Approval"        # approver(s) pending
    COMPLETED = "Completed"      # workflow finished successfully
    ABORTED = "Aborted"          # cancelled mid-way
