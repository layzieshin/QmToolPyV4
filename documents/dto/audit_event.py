"""Audit event DTO for compliance logging.

IMPORTANT: This DTO is used for TYPE DEFINITIONS only!
Audit events are NOT stored in a separate table.
All audit logging is done via AppContext.log_controller (central QM-Logging).

Comments in the 'comments' table are for DOCX/PDF review comments, NOT audit logs.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class AuditAction(Enum):
    """Audit action types for document lifecycle."""

    # Document Lifecycle
    DOCUMENT_CREATED = "document_created"
    DOCUMENT_IMPORTED = "document_imported"
    DOCUMENT_DELETED = "document_deleted"

    # Metadata
    METADATA_UPDATED = "metadata_updated"
    TITLE_CHANGED = "title_changed"
    TYPE_CHANGED = "type_changed"

    # Workflow
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_ABORTED = "workflow_aborted"
    STATUS_CHANGED = "status_changed"

    # Assignments
    ROLES_ASSIGNED = "roles_assigned"
    ROLES_UPDATED = "roles_updated"
    ROLES_CLEARED = "roles_cleared"

    # Versions
    VERSION_BUMPED = "version_bumped"
    MAJOR_VERSION_CREATED = "major_version_created"
    MINOR_VERSION_CREATED = "minor_version_created"
    REVISION_CREATED = "revision_created"

    # Files
    FILE_CHECKED_IN = "file_checked_in"
    FILE_UPLOADED = "file_uploaded"
    PDF_GENERATED = "pdf_generated"
    PDF_SIGNED = "pdf_signed"
    PDF_PUBLISHED = "pdf_published"

    # Export
    CONTROLLED_COPY_CREATED = "controlled_copy_created"
    DOCUMENT_EXPORTED = "document_exported"

    # Access
    DOCUMENT_OPENED = "document_opened"
    DOCUMENT_VIEWED = "document_viewed"
    DOCUMENT_DOWNLOADED = "document_downloaded"

    # Security
    ACCESS_DENIED = "access_denied"
    VALIDATION_FAILED = "validation_failed"
    PERMISSION_DENIED = "permission_denied"

    # Archive
    DOCUMENT_ARCHIVED = "document_archived"
    DOCUMENT_OBSOLETED = "document_obsoleted"
    DOCUMENT_RESTORED = "document_restored"


class AuditSeverity(Enum):
    """Audit event severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True)
class AuditEvent:
    """
    Immutable audit log event (compliance-grade).

    Meets requirements for:
    - ISO 9001:2015 (Quality Management)
    - ISO 13485:2016 (Medical Devices)
    - 21 CFR Part 11 (Electronic Records)
    - EU GMP Annex 11 (Computerized Systems)
    """

    # ===== Core Fields (Required) =====

    event_id: str
    """Unique event ID (UUID)"""

    event_type:  AuditAction
    """Type of action performed"""

    occurred_at: datetime
    """When the event occurred (UTC, immutable)"""

    actor_id: str
    """User ID who performed the action"""

    actor_name: Optional[str] = None
    """User display name (for human readability)"""

    # ===== Document Context =====

    doc_id: Optional[str] = None
    """Document ID (if applicable)"""

    doc_title: Optional[str] = None
    """Document title at time of event"""

    doc_version: Optional[str] = None
    """Document version at time of event (e.g., '1.0')"""

    doc_status: Optional[str] = None
    """Document status at time of event"""

    # ===== Action Details =====

    action_result: str = "success"
    """Result:  'success', 'failure', 'denied', 'partial'"""

    reason: Optional[str] = None
    """User-provided reason/justification"""

    error_message: Optional[str] = None
    """Error message (if action failed)"""

    # ===== Change Tracking =====

    changes: Dict[str, Any] = field(default_factory=dict)
    """
    Before/after values for changed fields.
    Format: {'field_name': {'old': <value>, 'new': <value>}}
    """

    # ===== Additional Context =====

    metadata:  Dict[str, Any] = field(default_factory=dict)
    """
    Additional context specific to action type.
    Examples: 
    - Signature:  {'pdf_path': '...', 'signature_method': 'pkcs7'}
    - Export: {'destination': '...', 'format': 'pdf'}
    """

    severity: AuditSeverity = AuditSeverity.INFO
    """Event severity level"""

    # ===== Traceability =====

    ip_address: Optional[str] = None
    """Client IP address (if available)"""

    session_id: Optional[str] = None
    """Session ID for correlation"""

    request_id: Optional[str] = None
    """Request/transaction ID for tracing"""

    # ===== Security =====

    signature: Optional[str] = None
    """Cryptographic signature of event (optional, for tamper-evidence)"""

    hash:  Optional[str] = None
    """Hash of event data (for integrity verification)"""

    # ===== System Context =====

    module_version: Optional[str] = None
    """Version of documents module at time of event"""

    system_info: Optional[str] = None
    """Additional system information"""

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for storage/serialization.

        Returns:
            Dictionary representation
        """
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "occurred_at":  self.occurred_at.isoformat(),
            "actor_id": self.actor_id,
            "actor_name": self.actor_name,
            "doc_id": self.doc_id,
            "doc_title":  self.doc_title,
            "doc_version": self.doc_version,
            "doc_status": self.doc_status,
            "action_result": self.action_result,
            "reason": self.reason,
            "error_message": self.error_message,
            "changes":  self.changes,
            "metadata": self.metadata,
            "severity": self.severity.value,
            "ip_address": self.ip_address,
            "session_id":  self.session_id,
            "request_id": self.request_id,
            "signature":  self.signature,
            "hash": self.hash,
            "module_version": self.module_version,
            "system_info": self.system_info,
        }

    def to_log_string(self) -> str:
        """
        Convert to human-readable log string.

        Returns:
            Formatted log message
        """
        parts = [
            f"[{self.occurred_at.isoformat()}]",
            f"[{self.severity.value.upper()}]",
            f"{self.event_type.value}",
            f"by {self.actor_name or self.actor_id}",
        ]

        if self.doc_id:
            parts.append(f"on {self.doc_id}")

        if self.reason:
            parts.append(f"- {self.reason}")

        if self.action_result != "success":
            parts.append(f"[{self.action_result.upper()}]")

        if self.error_message:
            parts.append(f"Error: {self.error_message}")

        return " ".join(parts)