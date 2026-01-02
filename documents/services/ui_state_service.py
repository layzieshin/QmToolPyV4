"""UI state service (no IO).

Combines policy services to derive UI states (button enablement, etc.).
"""

from __future__ import annotations
from typing import Optional, Set, Iterable

from documents.dto.view_state import ViewState
from documents.dto.controls_state import ControlsState
from documents.enum.document_status import DocumentStatus
from documents.services.policy.permission_policy import PermissionPolicy
from documents.services.policy.workflow_policy import WorkflowPolicy


class UIStateService:
    """Derive view state flags from policy evaluation."""

    def __init__(
        self,
        *,
        permission_policy: PermissionPolicy,
        workflow_policy:  WorkflowPolicy
    ):
        """
        Args:
            permission_policy: Permission evaluation service
            workflow_policy: Workflow rules service
        """
        self._perm_policy = permission_policy
        self._wf_policy = workflow_policy

    def build_controls_state(
        self,
        *,
        status: DocumentStatus,
        doc_type: str,
        user_roles: Iterable[str],
        assigned_roles: Iterable[str],
        workflow_active: bool,
        can_open_file: bool = False,
        user_id: Optional[str] = None,
        owner_id: Optional[str] = None,
        workflow_starter_id: Optional[str] = None
    ) -> ControlsState:
        """
        Build complete UI control state.

        Args:
            status: Current document status
            doc_type:  Document type
            user_roles:  User's module roles
            assigned_roles: User's assigned roles on this document
            workflow_active: Is workflow active?
            can_open_file: Can file be opened?
            user_id: Current user ID
            owner_id:  Document owner ID
            workflow_starter_id: User who started workflow

        Returns:
            ControlsState DTO
        """
        roles = set(user_roles) | set(assigned_roles)

        # Can open?
        can_open = can_open_file

        # Can copy?  (only EFFECTIVE documents)
        can_copy = (status == DocumentStatus.EFFECTIVE)

        # Can assign roles?
        can_assign_roles = self._perm_policy.can_perform(
            action_id="assign_roles",
            roles=roles
        )

        # Can archive?
        if status == DocumentStatus.EFFECTIVE:
            can_archive = self._perm_policy.can_perform(action_id="obsolete", roles=roles)
        elif status == DocumentStatus.OBSOLETE:
            can_archive = self._perm_policy.can_perform(action_id="archive", roles=roles)
        else:
            can_archive = False

        # Workflow toggle
        if status == DocumentStatus.DRAFT and not workflow_active:
            workflow_text = "Workflow starten"
            can_toggle_workflow = self._perm_policy.can_perform(action_id="start_workflow", roles=roles)
        elif workflow_active:
            workflow_text = "Workflow abbrechen"
            # Can abort if:  ADMIN/QMB or workflow starter
            is_admin = bool({"ADMIN", "QMB"} & set(user_roles))
            is_starter = (
                user_id and workflow_starter_id and
                str(user_id).strip().lower() == str(workflow_starter_id).strip().lower()
            )
            can_toggle_workflow = is_admin or is_starter
        else:
            workflow_text = "Kein aktiver Workflow"
            can_toggle_workflow = False

        # Next step
        allowed_actions = self._wf_policy.allowed_transitions(status)
        next_action = allowed_actions[0] if allowed_actions else None

        # Check permission for next action
        can_next = False
        if next_action:
            can_next = self._perm_policy.can_perform(action_id=next_action, roles=roles)

            # Check separation of duties
            if can_next and user_id and owner_id:
                if self._perm_policy.violates_separation_of_duties(
                    action_id=next_action,
                    actor_id=user_id,
                    owner_id=owner_id,
                    doc_type=doc_type
                ):
                    can_next = False

        action_labels = {
            "submit_review": "Zur Prüfung einreichen",
            "approve":  "Freigeben",
            "publish": "Veröffentlichen",
            "create_revision": "Revision erstellen",
            "obsolete": "Außer Kraft setzen",
            "archive": "Archivieren",
        }
        next_text = action_labels.get(next_action or "", "Nächster Schritt")

        # Back to draft?
        can_back_to_draft = (
            status in (DocumentStatus.REVIEW, DocumentStatus.APPROVED) and
            self._perm_policy.can_perform(action_id="back_to_draft", roles=roles)
        )

        return ControlsState(
            can_open=can_open,
            can_copy=can_copy,
            can_assign_roles=can_assign_roles,
            can_archive=can_archive,
            can_next=can_next,
            can_back_to_draft=can_back_to_draft,
            can_toggle_workflow=can_toggle_workflow,
            workflow_text=workflow_text,
            next_text=next_text,
        )

    def build_state(self) -> ViewState:
        """
        Build a default view state (legacy method).

        Returns:
            ViewState with all flags disabled
        """
        return ViewState(
            can_edit=False,
            can_submit_review=False,
            can_approve=False,
            can_publish=False,
            can_archive=False,
        )