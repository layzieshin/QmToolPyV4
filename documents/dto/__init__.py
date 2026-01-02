"""DTOs for documents module.

Data Transfer Objects for clean communication between layers.
"""

from documents.dto.assignments import Assignments
from documents.dto.controls_state import ControlsState
from documents.dto.document_details import DocumentDetails

__all__ = [
    "Assignments",
    "ControlsState",
    "DocumentDetails",
]