"""
===============================================================================
Permission Policy – global/system-level permissions
-------------------------------------------------------------------------------
Purpose:
    Centralize coarse-grained, system-wide permissions that are independent
    from the document type (e.g., who can start/abort workflows, edit roles,
    or archive documents) based on the current user's global roles.

Design:
    - No database access here.
    - Stateless, pure computations from CurrentUser (+ optional context).

Integration:
    - Consumed by UIStateService or dedicated services before executing actions.
===============================================================================
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Set

from documentlifecycle.models.system_role import SystemRole


@dataclass(slots=True)
class CurrentUser:
    """
    Minimal user shape for policy decisions.

    Fields
    ------
    id : int
        Current user's unique identifier.
    system_roles : set[SystemRole]
        Global roles in the host application (Admin, QMB, User, Viewer).
    can_start_workflow : bool
        Admin-granted flag: user may start workflows even if not Admin/QMB.
    """
    id: int
    system_roles: Set[SystemRole]
    can_start_workflow: bool = False


class PermissionPolicy:
    """
    Evaluate global permissions irrespective of a concrete document.

    Rules (as provided by product decisions):
      - Start Workflow: Admin/QMB OR explicit (can_start_workflow == True)
      - Abort Workflow: workflow starter OR QMB OR Admin
      - Edit Roles: QMB/Admin
      - Archive: QMB/Admin
    """

    def can_start_workflow(self, user: CurrentUser) -> bool:
        """Return True if the user may start a workflow anywhere."""
        return (
            SystemRole.ADMIN in user.system_roles
            or SystemRole.QMB in user.system_roles
            or user.can_start_workflow
        )

    def can_abort_workflow(self, user: CurrentUser, starter_user_id: int | None) -> bool:
        """
        Return True if the user can abort a running workflow.

        Parameters
        ----------
        user : CurrentUser
            Actor attempting to abort.
        starter_user_id : Optional[int]
            User id of whoever started the active workflow (if known).
        """
        return (
            (starter_user_id is not None and user.id == starter_user_id)
            or SystemRole.QMB in user.system_roles
            or SystemRole.ADMIN in user.system_roles
        )

    def can_edit_roles(self, user: CurrentUser) -> bool:
        """Return True if the user may edit per-document role assignments."""
        return SystemRole.QMB in user.system_roles or SystemRole.ADMIN in user.system_roles

    def can_archive(self, user: CurrentUser) -> bool:
        """Return True if the user may archive published documents."""
        return SystemRole.QMB in user.system_roles or SystemRole.ADMIN in user.system_roles
