"""Permission policy service.

Centralizes access control for the Documents module.

Key principles (Target Design A):
- System roles (USER/ADMIN/QMB) grant administrative capabilities only.
- Signing roles (AUTHOR/REVIEWER/APPROVER) are document-scoped assignments.
- JSON policy is the single source of truth for role->action permissions and signing chain mapping.
- Context constraints (owner/status/signature history) are evaluated generically here
  (no hard-coded "gates" in controllers or UI state derivation).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Set, Tuple
import json
import logging

logger = logging.getLogger(__name__)


SIGNING_ACTIONS: Set[str] = {"submit_review", "approve", "publish"}


@dataclass(frozen=True)
class AccessContext:
    """Context for access evaluation."""

    actor_id: str
    owner_id: Optional[str] = None
    status: Optional[str] = None  # String status name (e.g. "DRAFT")
    doc_type: Optional[str] = None

    assigned_roles: Tuple[str, ...] = ()
    system_roles: Tuple[str, ...] = ()

    # Signature rows: {role, username, signed_at, comment, ...}
    signatures: Tuple[Dict[str, Any], ...] = ()


class PermissionPolicy:
    """Evaluates permissions based on documents_permissions_policy.json."""

    def __init__(
        self,
        *,
        role_actions: Dict[str, Set[str]],
        system_role_mapping: Dict[str, Set[str]],
        separation_of_duties: Dict[str, Any],
        signing_chain: Dict[str, str],
    ) -> None:
        self._role_actions = role_actions or {}
        self._system_role_mapping = system_role_mapping or {}
        self._separation = separation_of_duties or {}
        self._signing_chain = {
            str(k).strip().lower(): str(v).strip().upper()
            for k, v in (signing_chain or {}).items()
            if str(k).strip() and str(v).strip()
        }

        # Defensive defaults: system roles do NOT expand to signing roles.
        if not self._system_role_mapping:
            self._system_role_mapping = {
                "ADMIN": {"ADMIN"},
                "QMB": {"QMB"},
                "USER": {"USER"},
            }

        # Defensive default signing chain (used only if JSON does not define it)
        if not self._signing_chain:
            self._signing_chain = {
                "submit_review": "AUTHOR",
                "approve": "REVIEWER",
                "publish": "APPROVER",
            }

    @classmethod
    def load_from_directory(cls, directory: str | Path) -> "PermissionPolicy":
        """Load policy from documents_permissions_policy.json."""
        base = Path(directory)
        policy_file = base / "documents_permissions_policy.json"

        data: Dict[str, Any] = {}
        if policy_file.exists():
            try:
                data = json.loads(policy_file.read_text(encoding="utf-8"))
                logger.info("Loaded permission policy from %s", policy_file)
            except Exception as ex:
                logger.error("Failed to load permission policy: %s", ex)
                data = {}
        else:
            logger.warning("Permission policy file not found: %s", policy_file)

        role_actions: Dict[str, Set[str]] = {}
        raw_roles = data.get("role_permissions", {}) or {}
        if isinstance(raw_roles, dict):
            for role, actions in raw_roles.items():
                role_actions[str(role).strip().upper()] = {
                    str(a).strip().lower()
                    for a in (actions or [])
                    if str(a).strip()
                }

        system_role_mapping: Dict[str, Set[str]] = {}
        raw_map = data.get("system_role_mapping", {}) or {}
        if isinstance(raw_map, dict):
            for sys_role, module_roles in raw_map.items():
                system_role_mapping[str(sys_role).strip().upper()] = {
                    str(r).strip().upper()
                    for r in (module_roles or [])
                    if str(r).strip()
                }

        separation = data.get("separation_of_duties", {}) or {}
        if not isinstance(separation, dict):
            separation = {}

        signing_chain_raw = data.get("signing_chain", {}) or {}
        if not isinstance(signing_chain_raw, dict):
            signing_chain_raw = {}

        return cls(
            role_actions=role_actions,
            system_role_mapping=system_role_mapping,
            separation_of_duties=separation,
            signing_chain=signing_chain_raw,
        )

    def expand_system_roles(self, roles: Iterable[str]) -> Set[str]:
        """Expand system roles to additional roles (if configured)."""
        expanded: Set[str] = set()

        for role in roles or []:
            role_upper = str(role).strip().upper()
            if not role_upper:
                continue
            expanded.add(role_upper)

            if role_upper in self._system_role_mapping:
                expanded.update(self._system_role_mapping[role_upper])

        return expanded

    def can_perform(self, *, action_id: str, roles: Iterable[str]) -> bool:
        """Return True if any of the given roles can perform the action."""
        action = (action_id or "").strip().lower()
        if not action:
            return False

        expanded_roles = self.expand_system_roles(roles)

        for role in expanded_roles:
            allowed_actions = self._role_actions.get(role, set())

            if "*" in allowed_actions:
                return True

            if action in allowed_actions:
                return True

            # Action aliases (defensive)
            if any(alias in allowed_actions for alias in self._action_aliases(action)):
                return True

        return False

    def required_assigned_role(self, *, action_id: str) -> Optional[str]:
        """Return the document-scoped role required to execute this action (signing chain)."""
        action = (action_id or "").strip().lower()
        return self._signing_chain.get(action)

    def can_execute(self, *, action_id: str, ctx: AccessContext) -> Tuple[bool, Optional[str]]:
        """Evaluate whether the actor may execute the given action in context.

        Returns:
            (allowed, reason_if_denied)
        """
        action = (action_id or "").strip().lower()
        if not action:
            return False, "Ungültige Aktion."

        actor = (ctx.actor_id or "").strip().lower()
        if not actor:
            return False, "Kein Benutzerkontext."

        system_roles = {str(r).strip().upper() for r in (ctx.system_roles or ()) if str(r).strip()}
        assigned_roles = {str(r).strip().upper() for r in (ctx.assigned_roles or ()) if str(r).strip()}
        status = (ctx.status or "").strip().upper()

        # Base RBAC (JSON): union of system roles and assigned roles.
        base_roles = set(system_roles) | set(assigned_roles)
        if not self.can_perform(action_id=action, roles=base_roles):
            return False, "Keine Berechtigung für diese Aktion."

        # === Context constraints ===

        # start_workflow: owner-only, except ADMIN/QMB
        if action == "start_workflow":
            is_admin = bool({"ADMIN", "QMB"} & system_roles)
            owner = (ctx.owner_id or "").strip().lower()
            if not is_admin:
                if not owner:
                    return False, "Dokumenten-Eigentümer unbekannt."
                if actor != owner:
                    return False, "Nur der Dokumenten-Eigentümer darf den Workflow starten."

                # Owner cannot start workflow once approved/archived; QMB/ADMIN may.
                if status in {"APPROVED", "ARCHIVED"}:
                    return False, "Workflow kann in diesem Status nicht vom Eigentümer gestartet werden."

        # Signing actions require document-scoped assigned role.
        if action in SIGNING_ACTIONS:
            required_role = self.required_assigned_role(action_id=action)
            if required_role and required_role not in assigned_roles:
                return False, f"Keine Berechtigung: Rolle '{required_role}' ist für diesen Schritt nicht zugewiesen."

            # Separation of duties: reviewer cannot publish if they already approved.
            if (
                action == "publish"
                and self._separation.get("reviewer_cannot_publish_if_reviewed", True)
                and self._has_signed(ctx.signatures, role="approve", username=actor)
            ):
                return False, "Separation of Duties: Wer geprüft hat, darf nicht selbst freigeben."

        return True, None

    @staticmethod
    def _has_signed(signatures: Iterable[Dict[str, Any]], *, role: str, username: str) -> bool:
        role_n = (role or "").strip().lower()
        user_n = (username or "").strip().lower()
        if not role_n or not user_n:
            return False

        for row in signatures or []:
            try:
                r = str(row.get("role", "")).strip().lower()
                u = str(row.get("username", "")).strip().lower()
                if r == role_n and u == user_n:
                    return True
            except Exception:
                continue
        return False

    @staticmethod
    def _action_aliases(action: str) -> Set[str]:
        aliases_map = {
            "submit_review": {"submit", "submit_review", "send_for_review"},
            "approve": {"approve", "approve_document", "approval"},
            "publish": {"publish", "release", "activate"},
            "create_revision": {"create_revision", "revise"},
            "archive": {"archive"},
            "obsolete": {"obsolete", "deprecate"},
            "start_workflow": {"start_workflow", "begin_workflow"},
            "back_to_draft": {"back_to_draft", "reject", "return_to_draft"},
        }
        return aliases_map.get(action, {action})
