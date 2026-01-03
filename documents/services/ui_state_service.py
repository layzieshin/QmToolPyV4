"""UI state service - derives button states from policies.

Uses STRING comparison for status to avoid enum class mismatch.
"""

from __future__ import annotations
from typing import Optional, Iterable, Any
import logging

from documents.dto.controls_state import ControlsState

logger = logging.getLogger(__name__)


class UIStateService:
    """Leitet UI-States aus Policy-Evaluation ab."""

    def __init__(self, *, permission_policy, workflow_policy):
        self._perm_policy = permission_policy
        self._wf_policy = workflow_policy

    def build_controls_state(
        self,
        *,
        status: Any,  # Accepts Enum or String
        doc_type: str,
        user_roles: Iterable[str],
        assigned_roles: Iterable[str],
        workflow_active: bool,
        can_open_file: bool = False,
        user_id: Optional[str] = None,
        owner_id: Optional[str] = None,
        workflow_starter_id: Optional[str] = None
    ) -> ControlsState:
        """Build complete UI control state."""

        # Normalize status to string
        status_name = self._to_status_name(status)

        # Expand system roles to module roles
        user_roles_set = set(str(r).upper() for r in user_roles)
        expanded_roles = self._perm_policy.expand_roles(user_roles_set)

        # Add document-specific assigned roles
        for r in assigned_roles:
            expanded_roles.add(str(r).upper())

        logger.debug(
            f"UIState: status={status_name}, user_roles={user_roles_set}, expanded={expanded_roles}"
        )

        # === Basic Actions ===
        can_open = can_open_file
        can_copy = (status_name == "EFFECTIVE")

        # === Assignment - only ADMIN/QMB/Owner/Workflow-Starter ===
        can_assign_roles = False
        if status_name == "DRAFT":
            can_assign_roles = self._perm_policy.can_assign_roles(
                user_roles=user_roles_set,
                user_id=user_id or "",
                owner_id=owner_id or "",
                workflow_starter_id=workflow_starter_id
            )

        # === Archive ===
        can_archive = False
        if status_name == "EFFECTIVE":
            can_archive = self._perm_policy.can_perform(action_id="obsolete", roles=expanded_roles)
        elif status_name == "OBSOLETE":
            can_archive = self._perm_policy.can_perform(action_id="archive", roles=expanded_roles)

        # === Workflow Toggle ===
        if status_name == "DRAFT" and not workflow_active:
            workflow_text = "Workflow starten"
            can_toggle_workflow = self._perm_policy.can_perform(
                action_id="start_workflow", roles=expanded_roles
            )
        elif workflow_active:
            workflow_text = "Workflow abbrechen"
            is_admin = bool({"ADMIN", "QMB"} & user_roles_set)
            is_starter = (
                user_id and workflow_starter_id and
                str(user_id).lower() == str(workflow_starter_id).lower()
            )
            can_toggle_workflow = is_admin or is_starter
        else:
            workflow_text = "Workflow starten"
            can_toggle_workflow = False

        # === Next Step ===
        allowed_actions = self._wf_policy.allowed_transitions(status)
        logger.debug(f"Allowed actions for {status_name}: {allowed_actions}")

        next_action = None
        can_next = False

        for action in allowed_actions:
            action_norm = str(action).strip().lower()

            # HARD GATE: action requires the corresponding assigned module role
            # (prevents "everyone can forward" even if system roles expand broadly)
            required_role = {
                "submit_review": "AUTHOR",
                "approve": "REVIEWER",
                "publish": "APPROVER",
            }.get(action_norm)

            is_admin = bool({"ADMIN", "QMB"} & user_roles_set)
            if required_role and (not is_admin) and (required_role not in expanded_roles):
                logger.debug(
                    f"Action {action} blocked: missing assigned role {required_role}"
                )
                continue

            if self._perm_policy.can_perform(action_id=action, roles=expanded_roles):
                # Check separation of duties
                if user_id and owner_id:
                    if self._perm_policy.violates_separation_of_duties(
                        action_id=action,
                        actor_id=user_id,
                        owner_id=owner_id,
                        doc_type=doc_type
                    ):
                        logger.debug(f"Action {action} blocked by separation of duties")
                        continue

                next_action = action
                can_next = True
                break

        action_labels = {
            "submit_review": "Zur Prüfung einreichen",
            "approve": "Akzeptieren",   # <- FIX: was previously "Freigeben" in your description
            "publish": "Freigeben",
            "create_revision": "Revision erstellen",
            "obsolete": "Außer Kraft setzen",
            "archive": "Archivieren",
        }
        next_text = action_labels.get(str(next_action or ""), "Nächster Schritt")

        # === Back to Draft ===
        can_back_to_draft = False
        if status_name in ("REVIEW", "APPROVED"):
            can_back_to_draft = self._perm_policy.can_perform(
                action_id="back_to_draft", roles=expanded_roles
            )

        result = ControlsState(
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

        logger.debug(
            f"Controls: can_next={can_next}, can_back={can_back_to_draft}, can_workflow={can_toggle_workflow}"
        )
        return result

    def _to_status_name(self, status: Any) -> str:
        """Convert any status to uppercase string."""
        if status is None:
            return ""
        if hasattr(status, "name"):
            return str(status.name).upper()
        if hasattr(status, "value"):
            return str(status.value).upper()
        return str(status).strip().upper()
