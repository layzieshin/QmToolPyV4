"""
===============================================================================
UI State Service – compose policies into view-facing state
-------------------------------------------------------------------------------
Purpose:
    Build a DocumentLifecycleUIState for a given (doc_id, user) combination by
    combining global permissions and workflow rules.

Design:
    - Pure read side: fetch the document once, then apply policies.
    - No side effects or writes; no popups/UI code here.

Inputs:
    - DocumentRepository (read)
    - RoleRepository (read via WorkflowPolicy)
    - PermissionPolicy (system roles)
    - WorkflowPolicy (phase & validity rules)
===============================================================================
"""
from __future__ import annotations
from typing import Optional

from documentlifecycle.logic.repository.document_repository import DocumentRepository
from documentlifecycle.logic.repository.role_repository import RoleRepository
from documentlifecycle.logic.viewstate.ui_state import DocumentLifecycleUIState
from documentlifecycle.models.document_status import DocumentStatus
from ..policy.permission_policy import PermissionPolicy, CurrentUser
from ..policy.workflow_policy import WorkflowPolicy


class UIStateService:
    """
    Compose permission and workflow policies into a view-ready UI state.

    Responsibilities:
        - Decide button visibility (start/abort/sign/archive/edit roles).
        - Provide simple hints (expired, extension allowed, info string).

    Excludes:
        - Any persistence or real workflow transitions.
    """

    def __init__(self, docs: DocumentRepository, roles: RoleRepository) -> None:
        """
        Parameters
        ----------
        docs : DocumentRepository
            Read-only access to documents.
        roles : RoleRepository
            Access to per-document role assignments.
        """
        self._docs = docs
        self._perm = PermissionPolicy()
        self._wf = WorkflowPolicy(roles)

    def compute(
        self,
        *,
        doc_id: int,
        user: CurrentUser,
        workflow_starter_id: Optional[int] = None
    ) -> DocumentLifecycleUIState:
        """
        Compute a UI state for the selected document and current user.

        Parameters
        ----------
        doc_id : int
            Document identifier to compute UI state for.
        user : CurrentUser
            Current user context (system roles + flags).
        workflow_starter_id : Optional[int]
            Needed by abort policy (starter can abort).

        Returns
        -------
        DocumentLifecycleUIState
            Flags and hints for the view to render appropriately.
        """
        doc = self._docs.get_by_id(doc_id)
        state = DocumentLifecycleUIState()
        if not doc:
            return state

        # base: read & print always visible
        state.show_read = True
        state.show_print = True

        # phase
        phase = self._wf.derive_phase(doc)
        active = phase.active

        # workflow toggles
        state.show_workflow_start = (not active) and self._perm.can_start_workflow(user)
        state.show_workflow_abort = active and self._perm.can_abort_workflow(user, workflow_starter_id)

        # sign visibility for current phase
        state.show_sign = active and self._wf.can_user_sign_in_phase(doc=doc, user=user)

        # edit roles only while active and for QMB/Admin
        state.show_edit_roles = active and self._perm.can_edit_roles(user)

        # archive only on published and for QMB/Admin
        state.show_archive = (doc.status == DocumentStatus.PUBLISHED) and self._perm.can_archive(user)

        # validity hints
        state.highlight_expired = self._wf.is_expired(doc)
        state.can_extend_without_change = self._wf.can_extend_without_change(doc)

        # optional info hint
        if active and phase.required_role is not None:
            state.info_hint = f"Active phase: {phase.required_role.value}"

        return state
