"""
===============================================================================
Workflow Policy – document-type-independent workflow rules
-------------------------------------------------------------------------------
Purpose:
    Provide rules for active workflow phases, permission to sign in a phase,
    and validity highlighting. These computations are pure (no DB writes).

Decisions implemented:
    - Strict order: DRAFT -> IN_REVIEW -> APPROVED -> PUBLISHED -> ARCHIVED
    - Multiple Reviewers/Approvers allowed (assignments).
    - A person assigned as Reviewer MUST NOT also act as Approver in the same
      workflow cycle (soft-enforced here until signature records exist).
    - Editing during review implies falling back to Editing (handled elsewhere).

Integration:
    - Consumed by UIStateService (visibility) and services that execute steps.
===============================================================================
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone

from documentlifecycle.logic.repository.role_repository import RoleRepository
from documentlifecycle.models.document import Document
from documentlifecycle.models.document_status import DocumentStatus
from documentlifecycle.models.workflow_role import WorkflowRole
from .permission_policy import CurrentUser


@dataclass(slots=True)
class WorkflowPhase:
    """
    Derived runtime phase from the document's status.

    Fields
    ------
    active : bool
        True if the document is currently in an active workflow step
        (requires human sign-off).
    required_role : Optional[WorkflowRole]
        The role expected to act/sign in the current phase, if any.
    """
    active: bool
    required_role: WorkflowRole | None


class WorkflowPolicy:
    """
    Compute phase-related rules and validity hints for a document.

    Notes:
        - This class reads role assignments via RoleRepository to decide if a
          given user may sign in the current phase.
        - Signature persistence is not part of this policy; enforcing "the same
          person didn't sign as reviewer and approver" will be strict once the
          signature records exist.
    """

    def __init__(self, roles: RoleRepository) -> None:
        self._roles = roles

    # -------- Phase detection --------------------------------------------- #
    def derive_phase(self, doc: Document) -> WorkflowPhase:
        """
        Return the 'WorkflowPhase' derived from document status.

        DRAFT      -> inactive phase, expected role = AUTHOR
        IN_REVIEW  -> active phase, expected role = REVIEWER
        APPROVED   -> active phase, expected role = APPROVER
        others     -> inactive (PUBLISHED/ARCHIVED)
        """
        if doc.status == DocumentStatus.DRAFT:
            return WorkflowPhase(active=False, required_role=WorkflowRole.AUTHOR)
        if doc.status == DocumentStatus.IN_REVIEW:
            return WorkflowPhase(active=True, required_role=WorkflowRole.REVIEWER)
        if doc.status == DocumentStatus.APPROVED:
            return WorkflowPhase(active=True, required_role=WorkflowRole.APPROVER)
        return WorkflowPhase(active=False, required_role=None)

    # -------- Permissions per phase --------------------------------------- #
    def can_user_sign_in_phase(self, *, doc: Document, user: CurrentUser) -> bool:
        """
        Return True if 'user' is allowed to execute the sign action now.

        We check:
            1) The document must be in an active phase with a required role.
            2) The user must be assigned to that required role for this doc.
            3) Soft constraint: reviewer and approver must not be the same sole
               person (this becomes strict once signatures are persisted).
        """
        phase = self.derive_phase(doc)
        if not phase.active or phase.required_role is None:
            return False

        allowed_user_ids = self._roles.list_users_for_role(doc.id, role=phase.required_role)
        if user.id not in allowed_user_ids:
            return False

        if phase.required_role == WorkflowRole.APPROVER:
            reviewer_ids = set(self._roles.list_users_for_role(doc.id, WorkflowRole.REVIEWER))
            approver_ids = set(self._roles.list_users_for_role(doc.id, WorkflowRole.APPROVER))
            if reviewer_ids and approver_ids and reviewer_ids == approver_ids and len(approver_ids) == 1:
                # same single person for both roles -> block
                return False

        return True

    # -------- Validity / highlighting ------------------------------------- #
    def is_expired(self, doc: Document) -> bool:
        """
        Return True if the document's 'valid_until' date is exceeded.

        Timezone-safe approach: compare dates in the doc's tz if available.
        """
        if not doc.valid_until:
            return False
        now = datetime.now(timezone.utc).astimezone(doc.valid_until.tzinfo)
        return now.date() > doc.valid_until.date()

    def can_extend_without_change(self, doc: Document) -> bool:
        """
        Placeholder: check if settings allow a 2-year extension w/o change.

        Implementation will consider:
            - Document type is configured for extension.
            - Counters not exceeding the max allowed number (3).
            - Status must be PUBLISHED.

        Currently returns False until counters/settings are introduced.
        """
        if doc.status != DocumentStatus.PUBLISHED:
            return False
        return False
