"""Permission policy service (no IO).

TODO: Implement role-based checks and separation-of-duties rules.
"""
from __future__ import annotations

from typing import Iterable


class PermissionPolicy:
    """Evaluate permission rules for document actions."""

    def can_perform(self, *, action_id: str, roles: Iterable[str]) -> bool:
        """Return True if any role can perform the action.

        TODO: Implement action-to-role mapping.
        """
        _ = action_id
        _ = roles
        return False

    def violates_separation_of_duties(self, *, action_id: str, actor_id: str, owner_id: str) -> bool:
        """Check separation-of-duties constraints.

        TODO: Implement policy rules.
        """
        _ = action_id
        _ = actor_id
        _ = owner_id
        return False
