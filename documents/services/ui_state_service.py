"""UI state service - derives button states from policies.

Uses STRING comparison for status to avoid enum class mismatch.
"""

from __future__ import annotations
from typing import Optional, Iterable, Any, Dict
import logging

from documents.services.policy.permission_policy import AccessContext
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
        workflow_starter_id: Optional[str] = None,
        signatures: Optional[Iterable[Dict[str, Any]]] = None,
    ) -> ControlsState:
        """Build complete UI control state.

        Note:
            All permission decisions are delegated to PermissionPolicy.can_execute()
            to keep UI and controller behavior consistent.
        """
        status_name = self._to_status_name(status)

        user_id_n = (user_id or "").strip()
        owner_id_n = (owner_id or "").strip()

        ctx = AccessContext(
            actor_id=user_id_n,
            owner_id=owner_id_n or None,
            status=status_name,
            doc_type=doc_type,
            assigned_roles=tuple(assigned_roles or []),
            system_roles=tuple(user_roles or []),
            signatures=tuple(signatures or []),
        )

        # === Basic Actions ===
        can_open = bool(can_open_file)
        can_copy = (status_name == "EFFECTIVE")

        # === Assignment ===
        can_assign_roles = False
        if status_name == "DRAFT":
            ok, _ = self._perm_policy.can_execute(action_id="assign_roles", ctx=ctx)
            can_assign_roles = bool(ok)

        # === Archive ===
        can_archive = False
        if status_name == "EFFECTIVE":
            ok, _ = self._perm_policy.can_execute(action_id="archive", ctx=ctx)
            can_archive = bool(ok)

        # === Workflow toggle (start/abort) ===
        can_toggle_workflow = False
        workflow_text = "—"
        if workflow_active:
            ok, _ = self._perm_policy.can_execute(action_id="abort_workflow", ctx=ctx)
            can_toggle_workflow = bool(ok)
            workflow_text = "Workflow beenden" if can_toggle_workflow else "Workflow aktiv"
        else:
            ok, _ = self._perm_policy.can_execute(action_id="start_workflow", ctx=ctx)
            can_toggle_workflow = bool(ok)
            workflow_text = "Workflow starten" if can_toggle_workflow else "Workflow —"

        # === Back to draft ===
        can_back_to_draft = False
        if status_name in ("REVIEW", "APPROVED", "EFFECTIVE", "REVISION", "OBSOLETE"):
            ok, _ = self._perm_policy.can_execute(action_id="back_to_draft", ctx=ctx)
            can_back_to_draft = bool(ok)

        # === Next Step ===
        allowed_actions = self._wf_policy.allowed_transitions(status)
        logger.debug(f"Allowed actions for {status_name}: {allowed_actions}")

        next_action = None
        can_next = False

        for action in allowed_actions:
            ok, _ = self._perm_policy.can_execute(action_id=action, ctx=ctx)
            if ok:
                next_action = str(action).strip().lower()
                can_next = True
                break

        next_text = self._label_for_action(next_action) if next_action else "—"

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


    def _label_for_action(self, action_id: Optional[str]) -> str:
        """Return a human-readable label for an action.

        UI text is intentionally kept simple here to avoid coupling this service to i18n.
        The view layer may override/translate these labels.
        """
        a = (action_id or "").strip().lower()
        mapping = {
            "submit_review": "Zur Prüfung",
            "approve": "Prüfen",
            "publish": "Freigeben",
            "create_revision": "Revision",
            "obsolete": "Obsolet",
            "archive": "Archivieren",
            "back_to_draft": "Zurück zu Entwurf",
        }
        return mapping.get(a, a or "—")

    def _to_status_name(self, status: Any) -> str:
        """Convert any status to uppercase string."""
        if status is None:
            return ""
        if hasattr(status, "name"):
            return str(status.name).upper()
        if hasattr(status, "value"):
            return str(status.value).upper()
        return str(status).strip().upper()
