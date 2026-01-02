"""Permission policy service (no IO).

Evaluates role-based access control and separation of duties.
Reads from configuration files (JSON).
"""

from __future__ import annotations
from typing import Iterable, Set, Dict, Any
from pathlib import Path
import json


class PermissionPolicy:
    """
    Evaluate permission rules for document actions.

    Based on configuration from documents_permissions_policy.json.
    """

    def __init__(self, *, role_actions: Dict[str, Iterable[str]], separation_rules: Dict[str, bool]):
        """
        Args:
            role_actions: Map of role -> allowed actions (e.g., {"ADMIN": ["create", "edit", ...]})
            separation_rules: Separation of duties rules (e.g., {"no_self_review": true})
        """
        self._role_actions:  Dict[str, Set[str]] = {
            role. strip().upper(): {str(a).strip().lower() for a in actions or []}
            for role, actions in (role_actions or {}).items()
        }
        self._separation = {k: bool(v) for k, v in (separation_rules or {}).items()}

    @classmethod
    def load_from_directory(cls, directory: str | Path) -> "PermissionPolicy":
        """
        Load policy from documents_permissions_policy. json.

        Args:
            directory: Directory containing policy JSON files

        Returns:
            PermissionPolicy instance
        """
        base = Path(directory)
        policy_file = base / "documents_permissions_policy.json"

        data = {}
        if policy_file.exists():
            try:
                with policy_file. open("r", encoding="utf-8") as f:
                    data = json. load(f)
            except Exception:
                data = {}

        return cls(
            role_actions=data.get("role_permissions", {}),
            separation_rules=data.get("separation_of_duties", {})
        )

    def can_perform(self, *, action_id: str, roles: Iterable[str]) -> bool:
        """
        Return True if any role can perform the action.

        Args:
            action_id: Action identifier (e.g., "create", "edit", "submit_review")
            roles: User's roles (e.g., ["ADMIN", "AUTHOR"])

        Returns:
            True if user can perform action
        """
        action = (action_id or "").strip().lower()
        if not action:
            return False

        user_roles = {r.strip().upper() for r in (roles or [])}

        # Check if any user role has permission for this action
        for role in user_roles:
            allowed_actions = self._role_actions. get(role, set())
            if action in allowed_actions:
                return True

            # Check aliases (e.g., "submit_review" might also be "submit")
            if any(alias in allowed_actions for alias in self._action_aliases(action)):
                return True

        return False

    def violates_separation_of_duties(
        self,
        *,
        action_id: str,
        actor_id: str,
        owner_id: str,
        doc_type: str = ""
    ) -> bool:
        """
        Check separation-of-duties constraints.

        Rules:
        - no_self_review: Actor cannot review their own document
        - no_self_approval: Actor cannot approve their own document

        Args:
            action_id: Action being performed
            actor_id: User performing action
            owner_id:  Document owner
            doc_type:  Document type (some types may allow self-approval)

        Returns:
            True if action violates separation of duties
        """
        if not actor_id or not owner_id:
            return False

        actor = actor_id.strip().lower()
        owner = owner_id.strip().lower()

        if not actor or not owner:
            return False

        action = (action_id or "").strip().lower()

        # No self-review rule
        if action in ("review", "submit_review", "request_approval") and self._separation. get("no_self_review", False):
            if actor == owner:
                return True

        # No self-approval rule
        if action in ("approve", "publish") and self._separation.get("no_self_approval", False):
            # Some document types may explicitly allow self-approval
            # This would be checked via doc_type config, but for now we enforce it
            if actor == owner:
                return True

        return False

    def required_roles_for_action(self, action_id: str) -> Set[str]:
        """
        Get set of roles that can perform this action.

        Args:
            action_id: Action identifier

        Returns:
            Set of role names
        """
        action = (action_id or "").strip().lower()
        roles:  Set[str] = set()

        for role, actions in self._role_actions.items():
            if action in actions or any(alias in actions for alias in self._action_aliases(action)):
                roles.add(role)

        return roles

    @staticmethod
    def _action_aliases(action_id: str) -> Set[str]:
        """
        Get aliases for an action.

        Examples:
        - "submit_review" → {"submit", "submit_review"}
        - "approve" → {"approve", "approve_document"}
        """
        action = (action_id or "").strip().lower()

        # Define common aliases
        aliases_map = {
            "submit_review": {"submit", "submit_review", "send_for_review"},
            "approve":  {"approve", "approve_document", "approval"},
            "publish": {"publish", "release", "activate"},
            "create_revision": {"create_revision", "edit_revision", "revise"},
            "archive": {"archive", "obsolete", "deactivate"},
        }

        return aliases_map.get(action, {action})