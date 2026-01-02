"""Audit logging service for compliance.

Uses central QM-Logging from AppContext instead of own database table.
"""

from __future__ import annotations
from typing import Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime
from uuid import uuid4

if TYPE_CHECKING:
    from core.qm_logging.logic.log_controller import LogController

from documents.dto.audit_event import AuditEvent, AuditAction, AuditSeverity


class AuditService:
    """
    Compliance-grade audit logging using central QM-Logging system.

    Delegates to AppContext.log_controller for persistent, immutable logging.
    """

    def __init__(self, log_controller: "LogController"):
        """
        Args:
            log_controller: Central logging controller from AppContext
        """
        self._log = log_controller
        self._module = "documents"

    def log(self, event: AuditEvent) -> None:
        """
        Log audit event via central QM-Logging.

        Args:
            event: AuditEvent to log
        """
        # Convert to log_controller format
        self._log.log_event(
            module=self._module,
            event_type=event.event_type.value,
            user_id=event.actor_id,
            user_name=event.actor_name,
            severity=event.severity.value,
            message=event.to_log_string(),
            details={
                "event_id": event.event_id,
                "doc_id": event.doc_id,
                "doc_title": event.doc_title,
                "doc_version": event.doc_version,
                "doc_status": event.doc_status,
                "action_result": event.action_result,
                "reason": event.reason,
                "error_message": event.error_message,
                "changes": event.changes,
                "metadata": event.metadata,
                "ip_address": event.ip_address,
                "session_id": event.session_id,
            }
        )

    def log_action(
        self,
        *,
        action: AuditAction,
        actor_id:  str,
        actor_name:  Optional[str] = None,
        doc_id: Optional[str] = None,
        doc_title:  Optional[str] = None,
        doc_version: Optional[str] = None,
        doc_status: Optional[str] = None,
        reason: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
        metadata:  Optional[Dict[str, Any]] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        result: str = "success",
        error_message: Optional[str] = None
    ) -> AuditEvent:
        """
        Convenience method to log an action.

        Returns:
            Created AuditEvent (for reference, already logged)
        """
        event = AuditEvent(
            event_id=str(uuid4()),
            event_type=action,
            occurred_at=datetime.utcnow(),
            actor_id=actor_id,
            actor_name=actor_name,
            doc_id=doc_id,
            doc_title=doc_title,
            doc_version=doc_version,
            doc_status=doc_status,
            action_result=result,
            reason=reason,
            error_message=error_message,
            changes=changes or {},
            metadata=metadata or {},
            severity=severity,
        )

        self.log(event)
        return event

    def log_workflow_started(
        self,
        *,
        doc_id: str,
        doc_title: str,
        actor_id: str,
        actor_name: Optional[str] = None
    ) -> None:
        """Log workflow start event."""
        self.log_action(
            action=AuditAction.WORKFLOW_STARTED,
            actor_id=actor_id,
            actor_name=actor_name,
            doc_id=doc_id,
            doc_title=doc_title,
            severity=AuditSeverity.INFO
        )

    def log_workflow_aborted(
        self,
        *,
        doc_id:  str,
        doc_title:  str,
        actor_id:  str,
        actor_name:  Optional[str] = None,
        reason: Optional[str] = None
    ) -> None:
        """Log workflow abort event."""
        self.log_action(
            action=AuditAction.WORKFLOW_ABORTED,
            actor_id=actor_id,
            actor_name=actor_name,
            doc_id=doc_id,
            doc_title=doc_title,
            reason=reason,
            severity=AuditSeverity.WARNING
        )

    def log_status_changed(
        self,
        *,
        doc_id: str,
        doc_title: str,
        actor_id: str,
        actor_name: Optional[str] = None,
        old_status: str,
        new_status: str,
        reason: Optional[str] = None
    ) -> None:
        """Log status change event."""
        self.log_action(
            action=AuditAction.STATUS_CHANGED,
            actor_id=actor_id,
            actor_name=actor_name,
            doc_id=doc_id,
            doc_title=doc_title,
            reason=reason,
            changes={"status": {"old": old_status, "new": new_status}},
            severity=AuditSeverity.INFO
        )

    def log_roles_assigned(
        self,
        *,
        doc_id: str,
        doc_title: str,
        actor_id: str,
        actor_name: Optional[str] = None,
        assignments: Dict[str, list]
    ) -> None:
        """Log role assignment event."""
        self.log_action(
            action=AuditAction.ROLES_ASSIGNED,
            actor_id=actor_id,
            actor_name=actor_name,
            doc_id=doc_id,
            doc_title=doc_title,
            metadata={"assignments": assignments},
            severity=AuditSeverity.INFO
        )

    def log_metadata_updated(
        self,
        *,
        doc_id: str,
        doc_title: str,
        actor_id: str,
        actor_name: Optional[str] = None,
        changes: Dict[str, Any]
    ) -> None:
        """Log metadata update event."""
        self.log_action(
            action=AuditAction.METADATA_UPDATED,
            actor_id=actor_id,
            actor_name=actor_name,
            doc_id=doc_id,
            doc_title=doc_title,
            changes=changes,
            severity=AuditSeverity.INFO
        )

    def log_pdf_signed(
        self,
        *,
        doc_id: str,
        doc_title: str,
        actor_id: str,
        actor_name: Optional[str] = None,
        step:  str,
        pdf_path: str,
        reason: Optional[str] = None
    ) -> None:
        """Log PDF signature event."""
        self.log_action(
            action=AuditAction.PDF_SIGNED,
            actor_id=actor_id,
            actor_name=actor_name,
            doc_id=doc_id,
            doc_title=doc_title,
            reason=reason,
            metadata={"step": step, "pdf_path": pdf_path},
            severity=AuditSeverity.INFO
        )

    def log_access_denied(
        self,
        *,
        doc_id: Optional[str],
        actor_id: str,
        actor_name: Optional[str] = None,
        action: str,
        reason: str
    ) -> None:
        """Log access denied event."""
        self.log_action(
            action=AuditAction.ACCESS_DENIED,
            actor_id=actor_id,
            actor_name=actor_name,
            doc_id=doc_id,
            reason=reason,
            metadata={"attempted_action": action},
            severity=AuditSeverity.WARNING,
            result="denied"
        )

    def log_error(
        self,
        *,
        doc_id: Optional[str],
        actor_id: str,
        actor_name: Optional[str] = None,
        action: AuditAction,
        error_message: str
    ) -> None:
        """Log error event."""
        self.log_action(
            action=action,
            actor_id=actor_id,
            actor_name=actor_name,
            doc_id=doc_id,
            error_message=error_message,
            severity=AuditSeverity.ERROR,
            result="failure"
        )