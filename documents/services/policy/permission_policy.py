"""Permission policy service.

Evaluates role-based access control and separation of duties.
Maps system roles (USER/ADMIN/QMB) to module roles (AUTHOR/REVIEWER/etc).
"""

from __future__ import annotations
from typing import Iterable, Set, Dict, Any, List
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


class PermissionPolicy:
    """
    Evaluate permission rules for document actions.

    Features:
    - System role → Module role mapping
    - Action-based permissions
    - Separation of duties enforcement
    """

    def __init__(
        self,
        *,
        role_actions: Dict[str, Iterable[str]],
        separation_rules: Dict[str, bool],
        system_role_mapping: Optional[Dict[str, List[str]]] = None
    ):
        """
        Args:
            role_actions: Map of role -> allowed actions
            separation_rules:  Separation of duties rules
            system_role_mapping: Map system roles to module roles
        """
        # Normalize:  all roles to UPPERCASE, all actions to lowercase
        self._role_actions:  Dict[str, Set[str]] = {
            role.strip().upper(): {str(a).strip().lower() for a in actions or []}
            for role, actions in (role_actions or {}).items()
        }
        self._separation = {k:  bool(v) for k, v in (separation_rules or {}).items()}

        # System role mapping (e.g., USER -> [AUTHOR], ADMIN -> [ADMIN, AUTHOR, ... ])
        self._system_role_mapping:  Dict[str, Set[str]] = {}
        for sys_role, module_roles in (system_role_mapping or {}).items():
            self._system_role_mapping[sys_role. upper()] = {
                r.upper() for r in module_roles
            }

        # Default mapping if not specified
        if not self._system_role_mapping:
            self._system_role_mapping = {
                "ADMIN": {"ADMIN", "AUTHOR", "EDITOR", "REVIEWER", "APPROVER"},
                "QMB": {"QMB", "AUTHOR", "EDITOR", "REVIEWER", "APPROVER"},
                "USER": {"AUTHOR"},
            }

        logger.debug(f"PermissionPolicy loaded with {len(self._role_actions)} roles")

    @classmethod
    def load_from_directory(cls, directory: str | Path) -> "PermissionPolicy":
        """Load policy from documents_permissions_policy.json."""
        base = Path(directory)
        policy_file = base / "documents_permissions_policy.json"

        data = {}
        if policy_file.exists():
            try:
                with policy_file.open("r", encoding="utf-8") as f:
                    data = json. load(f)
                logger.info(f"Loaded permission policy from {policy_file}")
            except Exception as ex:
                logger.error(f"Failed to load permission policy: {ex}")
                data = {}
        else:
            logger.warning(f"Permission policy file not found: {policy_file}")

        return cls(
            role_actions=data.get("role_permissions", {}),
            separation_rules=data.get("separation_of_duties", {}),
            system_role_mapping=data.get("system_role_mapping", None)
        )

    def expand_roles(self, roles:  Iterable[str]) -> Set[str]:
        """
        Expand system roles to include mapped module roles.

        Example:
            ["USER"] -> {"USER", "AUTHOR"}
            ["ADMIN"] -> {"ADMIN", "AUTHOR", "EDITOR", "REVIEWER", "APPROVER"}
        """
        expanded:  Set[str] = set()

        for role in roles:
            role_upper = str(role).strip().upper()
            expanded.add(role_upper)

            # Add mapped module roles
            if role_upper in self._system_role_mapping:
                expanded.update(self._system_role_mapping[role_upper])

        return expanded

    def can_perform(self, *, action_id: str, roles: Iterable[str]) -> bool:
        """
        Return True if any role can perform the action.

        Automatically expands system roles to module roles.
        """
        action = (action_id or "").strip().lower()
        if not action:
            return False

        # Expand system roles to module roles
        expanded_roles = self.expand_roles(roles)

        for role in expanded_roles:
            allowed_actions = self._role_actions. get(role, set())

            # Wildcard permission
            if "*" in allowed_actions:
                return True

            if action in allowed_actions:
                return True

            # Check aliases
            if any(alias in allowed_actions for alias in self._action_aliases(action)):
                return True

        return False

    def can_assign_roles(
        self,
        *,
        user_roles: Iterable[str],
        user_id: str,
        owner_id: str,
        workflow_starter_id: Optional[str] = None
    ) -> bool:
        """
        Check if user can assign roles.

        Allowed for:
        - ADMIN
        - QMB
        - Document owner (before workflow starts)
        - Workflow starter
        """
        roles_upper = {str(r).upper() for r in user_roles}

        # ADMIN/QMB can always assign
        if {"ADMIN", "QMB"} & roles_upper:
            return True

        # Owner can assign
        if user_id and owner_id:
            if str(user_id).lower() == str(owner_id).lower():
                return True

        # Workflow starter can assign
        if user_id and workflow_starter_id:
            if str(user_id).lower() == str(workflow_starter_id).lower():
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
        """Check separation-of-duties constraints."""
        if not actor_id or not owner_id:
            return False

        actor = actor_id.strip().lower()
        owner = owner_id.strip().lower()

        if not actor or not owner:
            return False

        action = (action_id or "").strip().lower()

        # No self-review rule
        if action in ("review", "submit_review") and self._separation. get("no_self_review", False):
            if actor == owner:
                return True

        # No self-approval rule
        if action in ("approve", "publish") and self._separation.get("no_self_approval", False):
            if actor == owner:
                return True

        return False

    def required_roles_for_action(self, action_id: str) -> Set[str]:
        """Get set of roles that can perform this action."""
        action = (action_id or "").strip().lower()
        roles:  Set[str] = set()

        for role, actions in self._role_actions. items():
            if "*" in actions or action in actions:
                roles. add(role)

        return roles

    @staticmethod
    def _action_aliases(action_id: str) -> Set[str]:
        """Get aliases for an action."""
        action = (action_id or "").strip().lower()

        aliases_map = {
            "submit_review": {"submit", "submit_review", "send_for_review"},
            "approve":  {"approve", "approve_document", "approval"},
            "publish": {"publish", "release", "activate"},
            "create_revision": {"create_revision", "revise"},
            "archive": {"archive"},
            "obsolete": {"obsolete", "deprecate"},
            "start_workflow": {"start_workflow", "begin_workflow"},
            "back_to_draft": {"back_to_draft", "reject", "return_to_draft"},
        }

        return aliases_map. get(action, {action})


# For type hints
from typing import Optional