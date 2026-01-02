# documents/logic/workflow_engine.py
"""
Workflow rules & guards for the Documents feature.

- Stateless: pure permission/guard logic, no storage or UI here.
- Policy-driven: uses configured transitions and permissions.
- Uses module roles (Author/Editor/Reviewer/Approver) plus per-document assignments.
"""

from __future__ import annotations
from typing import Iterable, Set, Optional, List

from documents.models.document_models import DocumentStatus
from documents.logic.documents_policy import DocumentsPolicy


def _norm(s: Iterable[str]) -> Set[str]:
    return {str(x).strip().upper() for x in (s or []) if str(x).strip()}


class WorkflowEngine:
    """Stateless rules engine; repository persists resulting changes."""

    def __init__(self, policy: DocumentsPolicy) -> None:
        self._policy = policy

    # ----------------- Guards for standard forward actions -------------------
    def allowed_actions(
        self,
        *,
        roles: Iterable[str],
        assigned: Iterable[str],
        status: DocumentStatus,
        doc_type: str,
        actor_id: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> List[str]:
        combined_roles = _norm(roles) | _norm(assigned)
        actions: List[str] = []
        for rule in self._policy.transitions_from(status, doc_type):
            if not self._policy.action_allowed_for_roles(rule.action, combined_roles):
                continue
            if self._policy.violates_separation_of_duties(
                action_id=rule.action,
                actor_id=actor_id,
                owner_id=owner_id,
                doc_type=doc_type,
            ):
                continue
            actions.append(rule.action)
        return actions

    def can_action(
        self,
        *,
        action_id: str,
        roles: Iterable[str],
        assigned: Iterable[str],
        status: DocumentStatus,
        doc_type: str,
        actor_id: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> bool:
        action = (action_id or "").strip().lower()
        return action in {
            a.strip().lower()
            for a in self.allowed_actions(
                roles=roles,
                assigned=assigned,
                status=status,
                doc_type=doc_type,
                actor_id=actor_id,
                owner_id=owner_id,
            )
        }

    # ----------------- Backwards / Out-of-band actions ----------------------
    
    def can_back_to_draft(self, *, roles: Iterable[str], assigned: Iterable[str], status: DocumentStatus) -> bool:
        return False

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

    # NACHHER (Zeile 104):
    def next_action(
            self,
            *,
            roles: Iterable[str],
            assigned: Iterable[str],
            status: DocumentStatus,
            doc_type: str,
            actor_id: Optional[str] = None,
            owner_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Suggest next forward action id for the 'Next' button.
        Returns one of:  'submit_review' | 'approve' | 'publish' | 'create_revision' | 'obsolete' | 'archive' | None
        """
        actions = self.allowed_actions(
            roles=roles,
            assigned=assigned,
            status=status,
            doc_type=doc_type,
            actor_id=actor_id,
            owner_id=owner_id,
        )
        return actions[0] if actions else None

    def next_status_for(self, action_id: str, current: DocumentStatus, doc_type: str) -> Optional[DocumentStatus]:
        aid = (action_id or "").strip().lower()
        for rule in self._policy.transitions_from(current, doc_type):
            if rule.action.strip().lower() == aid:
                return rule.to_status
        return None

    def requires_signature_for(self, action_id: str, doc_type: str) -> bool:
        """For forward actions we require a signature artifact if policy mandates signatures."""
        return bool(self._policy.required_signatures(doc_type, action_id))

    def requires_reason_for(self, action_id: str, target_status: DocumentStatus) -> bool:
        return self._policy.requires_reason(action_id, target_status)
