"""
===============================================================================
CurrentUser Provider Protocols & Defaults
-------------------------------------------------------------------------------
Purpose:
    Define a tiny abstraction for obtaining the current user context used by
    policies and services. This keeps controllers independent from the host
    application's user/session implementation.

Files:
    - CurrentUserProvider (Protocol)
    - DefaultCurrentUserProvider (development fallback)

Notes:
    - In production, prefer AppContextUserProvider which bridges the host's
      AppContext to the policy-facing CurrentUser.
===============================================================================
"""
from __future__ import annotations
from typing import Protocol, Set

from documentlifecycle.logic.policy.permission_policy import CurrentUser
from documentlifecycle.models.system_role import SystemRole


class CurrentUserProvider(Protocol):
    """Protocol for providers that yield the active CurrentUser."""
    def get_current_user(self) -> CurrentUser: ...


class DefaultCurrentUserProvider:
    """
    Development fallback provider.

    Behavior:
        - Returns a permissive Admin with can_start_workflow=True so that the
          UI can be explored without wiring the host session service first.
    """

    def __init__(self, user_id: int = 1) -> None:
        self._user_id = user_id

    def get_current_user(self) -> CurrentUser:
        roles: Set[SystemRole] = {SystemRole.ADMIN}
        return CurrentUser(id=self._user_id, system_roles=roles, can_start_workflow=True)
