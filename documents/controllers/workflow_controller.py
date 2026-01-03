"""WorkflowController - orchestrates workflow transitions.

Uses STRING comparison for status to avoid enum class mismatch.
"""

from __future__ import annotations
import logging
from typing import Callable, List, Optional, Tuple, Set, Any

logger = logging.getLogger(__name__)


class WorkflowController:
    """Orchestriert Workflow-Transitionen."""

    def __init__(
        self,
        *,
        repository,
        workflow_policy,
        permission_policy,
        current_user_provider:  Callable[[], Optional[object]],
    ) -> None:
        self._repo = repository
        self._wf_policy = workflow_policy
        self._perm_policy = permission_policy
        self._user_provider = current_user_provider

    def start_workflow(
        self,
        doc_id: str,
        *,
        user_roles: List[str],
        assigned_roles: Optional[List[str]] = None,
        ensure_assignments_callback: Optional[Callable[[], bool]] = None
    ) -> Tuple[bool, Optional[str]]:
        """Start workflow."""
        user = self._user_provider()
        if not user:
            return False, "Kein Benutzer angemeldet."

        record = self._repo.get(doc_id)
        if not record:
            return False, "Dokument nicht gefunden."

        # Check status (string comparison)
        status_name = self._to_status_name(record.status)
        if status_name != "DRAFT":
            return False, f"Workflow kann nur für Entwürfe gestartet werden (aktuell: {status_name})."

        # Expand and check permission
        all_roles = self._perm_policy.expand_roles(user_roles)
        if assigned_roles:
            all_roles.update(r.upper() for r in assigned_roles)

        if not self._perm_policy.can_perform(action_id="start_workflow", roles=all_roles):
            return False, "Keine Berechtigung zum Starten des Workflows."

        # Check assignments
        assignees = self._repo.get_assignees(doc_id)
        has_approver = bool(assignees. get("APPROVER"))

        if not has_approver:
            if ensure_assignments_callback and callable(ensure_assignments_callback):
                if not ensure_assignments_callback():
                    return False, "Rollenzuweisung abgebrochen."
                assignees = self._repo.get_assignees(doc_id)
                has_approver = bool(assignees.get("APPROVER"))

            if not has_approver:
                return False, "Mindestens ein Freigeber (Approver) muss zugewiesen sein."

        try:
            user_id = self._get_user_id(user)
            self._repo.set_workflow_active(doc_id, True, user_id)
            logger.info(f"Workflow started for {doc_id} by {user_id}")
            return True, None
        except Exception as ex:
            logger.error(f"Workflow start failed:  {ex}")
            return False, f"Workflow-Start fehlgeschlagen: {ex}"

    def abort_workflow(
        self,
        doc_id: str,
        reason: str,
        *,
        user_roles: List[str],
        assigned_roles: Optional[List[str]] = None
    ) -> Tuple[bool, Optional[str]]:
        """Abort workflow."""
        user = self._user_provider()
        if not user:
            return False, "Kein Benutzer angemeldet."

        if not reason or not reason.strip():
            return False, "Begründung erforderlich."

        record = self._repo.get(doc_id)
        if not record:
            return False, "Dokument nicht gefunden."

        if not self._repo.is_workflow_active(doc_id):
            return False, "Kein aktiver Workflow zum Abbrechen."

        user_roles_set = {r.upper() for r in user_roles}
        user_id = self._get_user_id(user)

        is_admin = bool({"ADMIN", "QMB"} & user_roles_set)
        starter_id = self._repo.get_workflow_starter(doc_id)
        is_starter = (
            starter_id and user_id and
            str(starter_id).lower() == str(user_id).lower()
        )

        if not (is_admin or is_starter):
            return False, "Nur ADMIN/QMB oder der Workflow-Starter können abbrechen."

        try:
            self._repo.set_workflow_active(doc_id, False)
            # Import status dynamically to use whatever enum is available
            from documents.enum. document_status import DocumentStatus
            self._repo.set_status(doc_id, DocumentStatus. DRAFT, user_id or "", reason)
            logger.info(f"Workflow aborted for {doc_id} by {user_id}")
            return True, None
        except Exception as ex:
            logger.error(f"Workflow abort failed: {ex}")
            return False, f"Workflow-Abbruch fehlgeschlagen: {ex}"

    def forward_transition(
        self,
        doc_id: str,
        reason: str,
        *,
        user_roles: List[str],
        assigned_roles: List[str],
    ) -> Tuple[bool, Optional[str]]:
        """Execute next workflow step."""
        user = self._user_provider()
        if not user:
            return False, "Kein Benutzer angemeldet."

        record = self._repo.get(doc_id)
        if not record:
            return False, "Dokument nicht gefunden."

        # Get allowed transitions
        allowed_actions = self._wf_policy. allowed_transitions(record.status)
        if not allowed_actions:
            status_name = self._to_status_name(record.status)
            return False, f"Keine Aktion möglich für Status '{status_name}'."

        # Find permitted action
        all_roles = self._perm_policy. expand_roles(user_roles)
        all_roles.update(r.upper() for r in assigned_roles)

        user_id = self._get_user_id(user)
        owner_id = self._repo.get_owner(doc_id)

        permitted_action = None
        for action in allowed_actions:
            if self._perm_policy.can_perform(action_id=action, roles=all_roles):
                if not self._perm_policy.violates_separation_of_duties(
                    action_id=action,
                    actor_id=user_id or "",
                    owner_id=owner_id or "",
                    doc_type=record. doc_type
                ):
                    permitted_action = action
                    break

        if not permitted_action:
            return False, "Keine Berechtigung für verfügbare Aktionen."

        # Check if reason required
        if self._wf_policy.requires_reason(permitted_action):
            if not reason or not reason.strip():
                return False, "Begründung erforderlich für diese Aktion."

        # Get next status
        next_status_name = self._wf_policy.next_status(
            action_id=permitted_action,
            status=record.status
        )
        if not next_status_name:
            return False, f"Kein Zielstatus für Aktion '{permitted_action}' definiert."

        try:
            # Convert string to enum
            from documents.enum.document_status import DocumentStatus
            next_status = DocumentStatus[next_status_name]

            self._repo.set_status(doc_id, next_status, user_id or "", reason or "")

            if next_status_name == "EFFECTIVE":
                self._repo.bump_minor_version(doc_id, user_id or "", reason)

            logger.info(f"Transition to {next_status_name} for {doc_id} by {user_id}")
            return True, None

        except Exception as ex:
            logger.error(f"Transition failed: {ex}")
            return False, f"Status-Update fehlgeschlagen: {ex}"

    def backward_to_draft(
        self,
        doc_id: str,
        reason: str,
        *,
        user_roles: List[str],
        assigned_roles: Optional[List[str]] = None
    ) -> Tuple[bool, Optional[str]]:
        """Revert to DRAFT."""
        user = self._user_provider()
        if not user:
            return False, "Kein Benutzer angemeldet."

        if not reason or not reason.strip():
            return False, "Begründung erforderlich."

        record = self._repo.get(doc_id)
        if not record:
            return False, "Dokument nicht gefunden."

        status_name = self._to_status_name(record.status)
        if status_name in ("EFFECTIVE", "OBSOLETE", "ARCHIVED"):
            return False, f"Zurücksetzen nicht möglich für Status '{status_name}'."

        if status_name == "DRAFT":
            return False, "Dokument ist bereits im Entwurf-Status."

        all_roles = self._perm_policy.expand_roles(user_roles)
        if assigned_roles:
            all_roles.update(r.upper() for r in assigned_roles)

        if not self._perm_policy.can_perform(action_id="back_to_draft", roles=all_roles):
            return False, "Keine Berechtigung zum Zurücksetzen."

        try:
            from documents.enum.document_status import DocumentStatus
            user_id = self._get_user_id(user)
            self._repo.set_status(doc_id, DocumentStatus.DRAFT, user_id or "", reason)
            logger.info(f"Reset to DRAFT for {doc_id} by {user_id}")
            return True, None
        except Exception as ex:
            logger. error(f"Reset failed: {ex}")
            return False, f"Zurücksetzen fehlgeschlagen: {ex}"

    def archive(
        self,
        doc_id: str,
        reason:  str,
        *,
        user_roles: List[str],
        assigned_roles: Optional[List[str]] = None
    ) -> Tuple[bool, Optional[str]]:
        """Archive document."""
        user = self._user_provider()
        if not user:
            return False, "Kein Benutzer angemeldet."

        if not reason or not reason.strip():
            return False, "Begründung erforderlich."

        record = self._repo.get(doc_id)
        if not record:
            return False, "Dokument nicht gefunden."

        status_name = self._to_status_name(record.status)

        if status_name == "EFFECTIVE":
            action_id = "obsolete"
            target_status_name = "OBSOLETE"
        elif status_name == "OBSOLETE":
            action_id = "archive"
            target_status_name = "ARCHIVED"
        else:
            return False, "Nur gültige oder obsolete Dokumente können archiviert werden."

        all_roles = self._perm_policy.expand_roles(user_roles)
        if assigned_roles:
            all_roles.update(r.upper() for r in assigned_roles)

        if not self._perm_policy.can_perform(action_id=action_id, roles=all_roles):
            return False, "Keine Berechtigung."

        try:
            from documents.enum.document_status import DocumentStatus
            target_status = DocumentStatus[target_status_name]
            user_id = self._get_user_id(user)
            self._repo.set_status(doc_id, target_status, user_id or "", reason)
            logger.info(f"Archive ({action_id}) for {doc_id} by {user_id}")
            return True, None
        except Exception as ex:
            logger.error(f"Archive failed: {ex}")
            return False, f"Archivierung fehlgeschlagen: {ex}"

    def _get_user_id(self, user: object) -> Optional[str]:
        """Extract user ID."""
        if not user:
            return None
        for attr in ("id", "user_id", "uid", "username"):
            val = getattr(user, attr, None)
            if val:
                return str(val)
        return None

    def _to_status_name(self, status: Any) -> str:
        """Convert status to string."""
        if status is None:
            return ""
        if hasattr(status, 'name'):
            return str(status.name).upper()
        if hasattr(status, 'value'):
            return str(status. value).upper()
        return str(status).strip().upper()