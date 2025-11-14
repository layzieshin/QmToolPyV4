# documents/logic/workflow_engine.py
"""
Workflow rules & guards for the Documents feature.

- Stateless: pure permission/guard logic, no storage or UI here.
- Uses fixed enums (DocumentStatus) and checks *both* global roles and
  per-document assigned roles.
- Keeps the set of transitions small & explicit.

Canonical global roles: ADMIN, QMB
Canonical assigned roles (per document): AUTHOR, REVIEWER, APPROVER
"""

from __future__ import annotations
from typing import Iterable, Set, Optional
from documents.models.document_models import DocumentStatus


def _norm(s: Iterable[str]) -> Set[str]:
    return {str(x).strip().upper() for x in (s or []) if str(x).strip()}


class WorkflowEngine:
    """Stateless rules engine; repository persists resulting changes."""

    # ----------------- Guards for standard forward actions -------------------
    def can_submit_review(self, *, roles: Iterable[str], assigned: Iterable[str], status: DocumentStatus) -> bool:
        r, a = _norm(roles), _norm(assigned)
        return (status == DocumentStatus.DRAFT) and ({"ADMIN", "QMB"} & r or "AUTHOR" in a)

    def can_request_approval(self, *, roles: Iterable[str], assigned: Iterable[str], status: DocumentStatus) -> bool:
        r, a = _norm(roles), _norm(assigned)
        return (status == DocumentStatus.IN_REVIEW) and ({"ADMIN", "QMB"} & r or "REVIEWER" in a)

    def can_publish(self, *, roles: Iterable[str], assigned: Iterable[str], status: DocumentStatus) -> bool:
        r, a = _norm(roles), _norm(assigned)
        return (status == DocumentStatus.APPROVAL) and ({"ADMIN", "QMB"} & r or "APPROVER" in a)

    # ----------------- Backwards / Out-of-band actions ----------------------
    def can_back_to_draft(self, *, roles: Iterable[str], assigned: Iterable[str], status: DocumentStatus) -> bool:
        # Rückwärts-Transition aus jedem Schritt außer Entwurf (ohne Signatur, aber mit Begründung).
        r = _norm(roles)
        return status != DocumentStatus.DRAFT and ({"ADMIN", "QMB"} & r)

    def can_abort_workflow(
        self,
        *,
        roles: Iterable[str],
        status: DocumentStatus,
        starter_user_id: str | None,
        current_user_id: str | None,
        active: bool,
    ) -> bool:
        # Abbrechen darf ADMIN/QMB oder der Starter, nur wenn der Workflow aktiv ist.
        if not active:
            return False
        r = _norm(roles)
        if {"ADMIN", "QMB"} & r:
            return True
        if starter_user_id and current_user_id and str(starter_user_id).strip().lower() == str(current_user_id).strip().lower():
            return True
        return False

    # ----------------- UX helpers (CTA texts / routing) ---------------------
    @staticmethod
    def next_action(*, roles: Iterable[str], assigned: Iterable[str], status: DocumentStatus) -> Optional[str]:
        """
        Suggest next forward action id for the 'Next' button.
        Returns one of: 'submit_review' | 'request_approval' | 'publish' | None
        """
        r, a = _norm(roles), _norm(assigned)
        if status == DocumentStatus.DRAFT and ({"ADMIN", "QMB"} & r or "AUTHOR" in a):
            return "submit_review"
        if status == DocumentStatus.IN_REVIEW and ({"ADMIN", "QMB"} & r or "REVIEWER" in a):
            return "request_approval"
        if status == DocumentStatus.APPROVAL and ({"ADMIN", "QMB"} & r or "APPROVER" in a):
            return "publish"
        return None

    @staticmethod
    def next_status_for(action_id: str, current: DocumentStatus) -> Optional[DocumentStatus]:
        aid = (action_id or "").strip().lower()
        if aid == "submit_review" and current == DocumentStatus.DRAFT:
            return DocumentStatus.IN_REVIEW
        if aid == "request_approval" and current == DocumentStatus.IN_REVIEW:
            return DocumentStatus.APPROVAL
        if aid == "publish" and current == DocumentStatus.APPROVAL:
            return DocumentStatus.PUBLISHED
        return None

    @staticmethod
    def requires_signature_for(action_id: str) -> bool:
        """For forward actions we require a signature artifact."""
        return (action_id or "").strip().lower() in {"submit_review", "request_approval", "publish"}

    @staticmethod
    def requires_reason_for(status_or_action) -> bool:
        """
        Ask for a change note (reason) only on *negative* / out-of-band states.
        The controller calls this with a status object.
        """
        try:
            name = str(getattr(status_or_action, "name", status_or_action)).upper()
        except Exception:
            name = str(status_or_action).upper()
        return name in {"ARCHIVED", "OBSOLETE"}
