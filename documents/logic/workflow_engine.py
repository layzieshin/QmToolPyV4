"""
Workflow rules & guards for the Documents feature.

- Allowed transitions driven by module roles and current status.
- Every status change will be signed in the GUI before calling repository.set_status(...)
- Adds helpers for a simpler CTA flow and back-to-draft operation.

Canonical roles: ADMIN, QMB, AUTHOR, REVIEWER, APPROVER, READER
"""

from __future__ import annotations
from typing import Iterable, Set
from documents.models.document_models import DocumentStatus


class WorkflowEngine:
    """Stateless rules engine; repository persists resulting changes."""

    # ---- Guards for standard actions ----------------------------------------
    def can_edit_metadata(self, roles: Set[str], status: DocumentStatus) -> bool:
        return (self._has_any(roles, {"ADMIN", "QMB", "AUTHOR"})
                and status in {DocumentStatus.DRAFT, DocumentStatus.IN_REVIEW})

    def can_check_out(self, roles: Set[str], status: DocumentStatus) -> bool:
        return self.can_edit_metadata(roles, status)

    def can_check_in(self, roles: Set[str], status: DocumentStatus) -> bool:
        return self.can_edit_metadata(roles, status)

    def can_submit_review(self, roles: Set[str], status: DocumentStatus) -> bool:
        return (self._has_any(roles, {"AUTHOR", "ADMIN", "QMB"})
                and status == DocumentStatus.DRAFT)

    def can_request_approval(self, roles: Set[str], status: DocumentStatus) -> bool:
        return (self._has_any(roles, {"REVIEWER", "QMB", "ADMIN"})
                and status == DocumentStatus.IN_REVIEW)

    def can_publish(self, roles: Set[str], status: DocumentStatus) -> bool:
        return (self._has_any(roles, {"APPROVER", "QMB", "ADMIN"})
                and status == DocumentStatus.APPROVAL)

    def can_obsolete(self, roles: Set[str], status: DocumentStatus) -> bool:
        return self._has_any(roles, {"ADMIN", "QMB"}) and status != DocumentStatus.OBSOLETE

    # ---- New: Back-to-draft from any status (admin/QMB) ---------------------
    def can_back_to_draft(self, roles: Set[str], status: DocumentStatus) -> bool:
        return self._has_any(roles, {"ADMIN", "QMB"}) and status != DocumentStatus.DRAFT

    # ---- UX helpers ----------------------------------------------------------
    @staticmethod
    def is_workflow_active(status: DocumentStatus) -> bool:
        """Active means: not in initial draft anymore."""
        return status in {DocumentStatus.IN_REVIEW, DocumentStatus.APPROVAL,
                          DocumentStatus.PUBLISHED, DocumentStatus.OBSOLETE}

    @staticmethod
    def next_action(roles: Set[str], status: DocumentStatus) -> str | None:
        """CTA used by 'Workflow starten/fortsetzen' in the GUI."""
        if status == DocumentStatus.DRAFT and ("AUTHOR" in {r.upper() for r in roles} or
                                               {"ADMIN", "QMB"} & {r.upper() for r in roles}):
            return "submit_review"
        if status == DocumentStatus.IN_REVIEW and {"REVIEWER", "QMB", "ADMIN"} & {r.upper() for r in roles}:
            return "request_approval"
        if status == DocumentStatus.APPROVAL and {"APPROVER", "QMB", "ADMIN"} & {r.upper() for r in roles}:
            return "publish"
        return None

    def require_change_note(self, _target_status: DocumentStatus) -> bool:
        # GUI verlangt ohnehin eine kurze Notiz; wir lassen True für Konsistenz
        return True

    # ---- Helpers -------------------------------------------------------------
    @staticmethod
    def _has_any(user_roles: Iterable[str], required: Iterable[str]) -> bool:
        ur = {str(r).upper() for r in user_roles}
        req = {str(r).upper() for r in required}
        return bool(ur & req)
