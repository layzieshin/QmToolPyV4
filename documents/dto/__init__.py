"""Data Transfer Objects for documents module.

DTOs are immutable data containers for transferring data between layers.
"""

from documents.dto.assignments import Assignments
from documents.dto.audit_event import AuditEvent, AuditAction, AuditSeverity
from documents.dto.controls_state import ControlsState
from documents.dto.document_details import DocumentDetails
from documents.dto.type_spec import TypeSpec

__all__ = [
    "Assignments",
    "AuditEvent",
    "AuditAction",
    "AuditSeverity",
    "ControlsState",
    "DocumentDetails",
    "TypeSpec",
]