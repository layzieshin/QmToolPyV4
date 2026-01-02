"""documents/services/policy/workflow_policy.py
================================================

Workflow policy (no IO).

This policy enforces the transition matrix defined in the integration analysis.
It is independent from GUI and persistence.

Transitions are evaluated based on:
- current status
- action id
- document type spec (settings-driven)

The policy does not decide *who* may perform actions; see PermissionPolicy.
"""
from __future__ import annotations

from dataclasses import dataclass

from documents.dto.document_type_spec import DocumentTypeSpec
from documents.enum.document_action import DocumentAction
from documents.enum.document_status import DocumentStatus


@dataclass(frozen=True, slots=True)
class Transition:
    """Single workflow transition definition."""

    from_status: DocumentStatus
    action: DocumentAction
    to_status: DocumentStatus


# Canonical transition matrix (hard enforced)
TRANSITIONS: tuple[Transition, ...] = (
    Transition(DocumentStatus.DRAFT, DocumentAction.SUBMIT_REVIEW, DocumentStatus.REVIEW),
    Transition(DocumentStatus.DRAFT, DocumentAction.APPROVE, DocumentStatus.APPROVED),
    Transition(DocumentStatus.REVIEW, DocumentAction.APPROVE, DocumentStatus.APPROVED),
    Transition(DocumentStatus.APPROVED, DocumentAction.PUBLISH, DocumentStatus.EFFECTIVE),
    Transition(DocumentStatus.EFFECTIVE, DocumentAction.CREATE_REVISION, DocumentStatus.REVISION),
    Transition(DocumentStatus.REVISION, DocumentAction.SUBMIT_REVIEW, DocumentStatus.REVIEW),
    Transition(DocumentStatus.EFFECTIVE, DocumentAction.OBSOLETE, DocumentStatus.OBSOLETE),
    Transition(DocumentStatus.OBSOLETE, DocumentAction.ARCHIVE, DocumentStatus.ARCHIVED),
)


class WorkflowPolicy:
    """Evaluate workflow transition rules."""

    def can_transition(
        self,
        *,
        status: DocumentStatus,
        action_id: str,
        type_spec: DocumentTypeSpec,
    ) -> bool:
        """Return True if the action is allowed and results in a valid next status."""
        try:
            _ = self.next_status(status=status, action_id=action_id, type_spec=type_spec)
            return True
        except ValueError:
            return False

    def next_status(
        self,
        *,
        status: DocumentStatus,
        action_id: str,
        type_spec: DocumentTypeSpec,
    ) -> DocumentStatus:
        """Resolve the next status for a given action.

        Raises:
            ValueError: if the transition is not allowed.
        """
        action = DocumentAction(action_id)

        # Type-gated transitions
        if action is DocumentAction.SUBMIT_REVIEW and not type_spec.requires_review:
            raise ValueError("Review is not enabled for this document type")
        if action is DocumentAction.APPROVE and not type_spec.requires_approval:
            raise ValueError("Approval is not enabled for this document type")
        if action is DocumentAction.PUBLISH and not type_spec.requires_approval:
            raise ValueError("Publish is not enabled for this document type")

        for t in TRANSITIONS:
            if t.from_status == status and t.action == action:
                return t.to_status

        raise ValueError(f"Transition not allowed: {status.value} --{action.value}--> ?")

    def is_editable(self, *, status: DocumentStatus) -> bool:
        """Return True if content/metadata may be edited in this status."""
        return status in (DocumentStatus.DRAFT, DocumentStatus.REVISION)

    def requires_reason(self, *, action_id: str) -> bool:
        """Return True if a reason is required for the action."""
        action = DocumentAction(action_id)
        return action is DocumentAction.OBSOLETE
