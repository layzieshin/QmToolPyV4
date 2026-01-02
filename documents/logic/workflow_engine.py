# documents/logic/workflow_engine.py
"""
Workflow rules & guards for the Documents feature.

- Stateless: pure permission/guard logic, no storage or UI here.
- Uses fixed enums (DocumentStatus) and checks *both* global roles and
  per-document assigned roles.
- Implements policy-driven workflow according to documents_workflow_transitions.json

Canonical global roles: ADMIN, QMB
Canonical assigned roles (per document): AUTHOR, EDITOR, REVIEWER, APPROVER
"""

from __future__ import annotations
from typing import Iterable, Set, Optional
from documents.models.document_models import DocumentStatus


def _norm(s: Iterable[str]) -> Set[str]:
    return {str(x).strip().upper() for x in (s or []) if str(x).strip()}


class WorkflowEngine:
    """Stateless rules engine; repository persists resulting changes."""

    # ----------------- Guards for workflow actions -------------------
    
    def can_submit_review(self, *, roles: Iterable[str], assigned: Iterable[str], status: DocumentStatus, 
                         requires_review: bool = True) -> bool:
        """
        DRAFT -> REVIEW (if document_type.requires_review == true)
        REVISION -> REVIEW (if document_type.requires_review == true)
        """
        r, a = _norm(roles), _norm(assigned)
        if not requires_review:
            return False
        return (status in (DocumentStatus.DRAFT, DocumentStatus.REVISION)) and \
               ({"ADMIN", "QMB"} & r or {"AUTHOR", "EDITOR"} & a)

    def can_approve(self, *, roles: Iterable[str], assigned: Iterable[str], status: DocumentStatus,
                   requires_review: bool = True) -> bool:
        """
        REVIEW -> APPROVED (after review)
        DRAFT -> APPROVED (if document_type.requires_review == false)
        """
        r, a = _norm(roles), _norm(assigned)
        # From REVIEW state
        if status == DocumentStatus.REVIEW:
            return {"ADMIN", "QMB"} & r or "APPROVER" in a
        # Direct from DRAFT (skip review)
        if status == DocumentStatus.DRAFT and not requires_review:
            return {"ADMIN", "QMB"} & r or "APPROVER" in a
        return False

    def can_publish(self, *, roles: Iterable[str], assigned: Iterable[str], status: DocumentStatus) -> bool:
        """APPROVED -> EFFECTIVE"""
        r, a = _norm(roles), _norm(assigned)
        return (status == DocumentStatus.APPROVED) and ({"ADMIN", "QMB"} & r or "APPROVER" in a)

    def can_create_revision(self, *, roles: Iterable[str], assigned: Iterable[str], status: DocumentStatus) -> bool:
        """EFFECTIVE -> REVISION"""
        r, a = _norm(roles), _norm(assigned)
        return (status == DocumentStatus.EFFECTIVE) and \
               ({"ADMIN", "QMB"} & r or {"AUTHOR", "EDITOR"} & a)

    def can_obsolete(self, *, roles: Iterable[str], assigned: Iterable[str], status: DocumentStatus) -> bool:
        """EFFECTIVE -> OBSOLETE (with reason required)"""
        r, a = _norm(roles), _norm(assigned)
        return (status == DocumentStatus.EFFECTIVE) and ({"ADMIN", "QMB"} & r or "APPROVER" in a)

    def can_archive(self, *, roles: Iterable[str], assigned: Iterable[str], status: DocumentStatus) -> bool:
        """OBSOLETE -> ARCHIVED"""
        r = _norm(roles)
        return (status == DocumentStatus.OBSOLETE) and ({"ADMIN", "QMB"} & r)

    # ----------------- Forbidden transitions check ----------------------
    
    def is_transition_forbidden(self, from_status: DocumentStatus, to_status: DocumentStatus) -> bool:
        """Check if a transition is explicitly forbidden"""
        forbidden = [
            (DocumentStatus.EFFECTIVE, DocumentStatus.DRAFT),
            (DocumentStatus.REVIEW, DocumentStatus.EFFECTIVE),
        ]
        # ARCHIVED cannot transition to any other status
        if from_status == DocumentStatus.ARCHIVED:
            return True
        return (from_status, to_status) in forbidden

    # ----------------- Backwards / Out-of-band actions ----------------------
    
    def can_back_to_draft(self, *, roles: Iterable[str], assigned: Iterable[str], status: DocumentStatus) -> bool:
        """Allow returning to draft from non-final states (ADMIN/QMB only)"""
        r = _norm(roles)
        # Cannot go back from EFFECTIVE, OBSOLETE, or ARCHIVED
        if status in (DocumentStatus.EFFECTIVE, DocumentStatus.OBSOLETE, DocumentStatus.ARCHIVED):
            return False
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
        """Abort active workflow (ADMIN/QMB or workflow starter)"""
        if not active:
            return False
        r = _norm(roles)
        if {"ADMIN", "QMB"} & r:
            return True
        if starter_user_id and current_user_id and \
           str(starter_user_id).strip().lower() == str(current_user_id).strip().lower():
            return True
        return False

    # ----------------- UX helpers (CTA texts / routing) ---------------------
    
    @staticmethod
    def next_action(*, roles: Iterable[str], assigned: Iterable[str], status: DocumentStatus,
                   requires_review: bool = True) -> Optional[str]:
        """
        Suggest next forward action id for the 'Next' button.
        Returns: 'submit_review' | 'approve' | 'publish' | 'create_revision' | 'obsolete' | 'archive' | None
        """
        r, a = _norm(roles), _norm(assigned)
        
        # DRAFT state
        if status == DocumentStatus.DRAFT:
            if requires_review and ({"ADMIN", "QMB"} & r or {"AUTHOR", "EDITOR"} & a):
                return "submit_review"
            elif not requires_review and ({"ADMIN", "QMB"} & r or "APPROVER" in a):
                return "approve"
        
        # REVIEW state
        if status == DocumentStatus.REVIEW and ({"ADMIN", "QMB"} & r or "APPROVER" in a):
            return "approve"
        
        # APPROVED state
        if status == DocumentStatus.APPROVED and ({"ADMIN", "QMB"} & r or "APPROVER" in a):
            return "publish"
        
        # REVISION state
        if status == DocumentStatus.REVISION:
            if requires_review and ({"ADMIN", "QMB"} & r or {"AUTHOR", "EDITOR"} & a):
                return "submit_review"
        
        # EFFECTIVE state
        if status == DocumentStatus.EFFECTIVE:
            if {"ADMIN", "QMB"} & r or {"AUTHOR", "EDITOR"} & a:
                return "create_revision"
        
        # OBSOLETE state
        if status == DocumentStatus.OBSOLETE and ({"ADMIN", "QMB"} & r):
            return "archive"
        
        return None

    @staticmethod
    def next_status_for(action_id: str, current: DocumentStatus, requires_review: bool = True) -> Optional[DocumentStatus]:
        """Determine the next status based on action and current status"""
        aid = (action_id or "").strip().lower()
        
        if aid == "submit_review":
            if current in (DocumentStatus.DRAFT, DocumentStatus.REVISION):
                return DocumentStatus.REVIEW
        
        if aid == "approve":
            if current == DocumentStatus.REVIEW:
                return DocumentStatus.APPROVED
            if current == DocumentStatus.DRAFT and not requires_review:
                return DocumentStatus.APPROVED
        
        if aid == "publish" and current == DocumentStatus.APPROVED:
            return DocumentStatus.EFFECTIVE
        
        if aid == "create_revision" and current == DocumentStatus.EFFECTIVE:
            return DocumentStatus.REVISION
        
        if aid == "obsolete" and current == DocumentStatus.EFFECTIVE:
            return DocumentStatus.OBSOLETE
        
        if aid == "archive" and current == DocumentStatus.OBSOLETE:
            return DocumentStatus.ARCHIVED
        
        return None

    @staticmethod
    def requires_signature_for(action_id: str) -> bool:
        """Determine if an action requires a signature based on document type configuration"""
        # Signatures are required for submit_review, approve, and publish
        # The actual requirement depends on document type's required_signatures field
        return (action_id or "").strip().lower() in {"submit_review", "approve", "publish"}

    @staticmethod
    def requires_reason_for(action_id: str) -> bool:
        """Determine if an action requires a reason/change note"""
        # Obsolete and archive actions require reasons
        aid = (action_id or "").strip().lower()
        return aid in {"obsolete", "archive", "back_to_draft"}
