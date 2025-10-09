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
from typing import Iterable, Set
from documents.models.document_models import DocumentStatus


def _norm(s: Iterable[str]) -> Set[str]:
    return {str(x).upper() for x in (s or [])}


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
    def next_action(*, roles: Iterable[str], assigned: Iterable[str], status: DocumentStatus) -> str | None:
        """Suggest CTA id for the 'Next Step' button."""
        r, a = _norm(roles), _norm(assigned)
        if status == DocumentStatus.DRAFT and ({"ADMIN", "QMB"} & r or "AUTHOR" in a):
            return "submit_review"
        if status == DocumentStatus.IN_REVIEW and ({"ADMIN", "QMB"} & r or "REVIEWER" in a):
            return "request_approval"
        if status == DocumentStatus.APPROVAL and ({"ADMIN", "QMB"} & r or "APPROVER" in a):
            return "publish"
        return None

    @staticmethod
    def require_change_note(target_status: DocumentStatus) -> bool:
        # Wir verlangen überall eine kurze Notiz – GUI setzt das durch.
        return True
