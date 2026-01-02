"""WorkflowController - orchestrates workflow transitions.

REFACTORED: Uses WorkflowPolicy and PermissionPolicy services.
"""

from __future__ import annotations
from typing import Callable, Optional, Tuple

from documents.repository.document_repository import DocumentRepository
from documents.services.policy. workflow_policy import WorkflowPolicy
from documents.services.policy. permission_policy import PermissionPolicy
from documents.models.document_models import DocumentStatus


class WorkflowController:
    """
    Orchestrates workflow transitions.

    REFACTORED:
    - Uses WorkflowPolicy for transition rules
    - Uses PermissionPolicy for authorization
    - Stateless (no caching)
    """

    def __init__(
        self,
        *,
        repository: DocumentRepository,
        workflow_policy: WorkflowPolicy,
        permission_policy: PermissionPolicy,
        current_user_provider:  Callable[[], Optional[object]]
    ) -> None:
        """
        Args:
            repository: Documents repository
            workflow_policy: Workflow rules service
            permission_policy: Permission evaluation service
            current_user_provider: Lambda that returns current user
        """
        self._repo = repository
        self._wf_policy = workflow_policy
        self._perm_policy = permission_policy
        self._user_provider = current_user_provider

    def start_workflow(
        self,
        doc_id: str,
        *,
        user_roles: list[str],
        ensure_assignments_callback: Optional[Callable[[], bool]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Start workflow (sets workflow_active=True).

        Args:
            doc_id: Document ID
            user_roles: User's roles
            ensure_assignments_callback:  Optional callback to ensure roles are assigned

        Returns:
            (success:  bool, error_msg: Optional[str])
        """
        user = self._user_provider()
        if not user:
            return False, "Kein Benutzer angemeldet."

        # Check permission
        if not self._perm_policy.can_perform(action_id="start_workflow", roles=user_roles):
            return False, "Keine Berechtigung zum Starten des Workflows."

        # Check if assignments are present
        assignees = self._repo.get_assignees(doc_id)
        if not any(assignees. get(role) for role in ("AUTHOR", "REVIEWER", "APPROVER")):
            if ensure_assignments_callback and callable(ensure_assignments_callback):
                if not ensure_assignments_callback():
                    return False, "Rollenzuweisung abgebrochen."
            else:
                return False, "Keine Rollen zugewiesen."

        # Start workflow
        try:
            user_id = self._get_user_id(user)
            self._repo.set_workflow_active(doc_id, True, user_id)
            return True, None
        except Exception as ex:
            return False, f"Workflow-Start fehlgeschlagen: {ex}"

    def abort_workflow(
        self,
        doc_id: str,
        password: str,
        reason: str,
        *,
        user_roles: list[str]
    ) -> Tuple[bool, Optional[str]]:
        """
        Abort workflow (Admin/QMB/Starter).

        Args:
            doc_id: Document ID
            password:  Confirmation password
            reason: Reason for abort
            user_roles: User's roles

        Returns:
            (success: bool, error_msg: Optional[str])
        """
        user = self._user_provider()
        if not user:
            return False, "Kein Benutzer angemeldet."

        # TODO: Validate password
        if not password:
            return False, "Passwort erforderlich."

        # Check permission
        record = self._repo.get(doc_id)
        if not record:
            return False, "Dokument nicht gefunden."

        # Admin/QMB can always abort
        if not self._perm_policy.can_perform(action_id="abort_workflow", roles=user_roles):
            # Check if user is workflow starter
            starter_id = self._repo.get_workflow_starter(doc_id)
            user_id = self._get_user_id(user)

            if not (starter_id and user_id and starter_id. lower() == user_id.lower()):
                return False, "Keine Berechtigung zum Abbrechen des Workflows."

        # Abort workflow
        try:
            user_id = self._get_user_id(user)
            self._repo.set_workflow_active(doc_id, False, user_id)
            self._repo.set_status(doc_id, DocumentStatus. DRAFT, user_id or "", reason)
            return True, None
        except Exception as ex:
            return False, f"Workflow-Abbruch fehlgeschlagen: {ex}"

    def forward_transition(
        self,
        doc_id: str,
        reason: str,
        *,
        user_roles: list[str],
        assigned_roles: list[str],
        sign_pdf_callback: Optional[Callable[[str, str], Optional[str]]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Execute next workflow step.

        Args:
            doc_id: Document ID
            reason: Reason/change note
            user_roles: User's module roles
            assigned_roles: User's assigned roles on this document
            sign_pdf_callback:  Optional signature callback (pdf_path, reason) -> signed_path

        Returns:
            (success: bool, error_msg: Optional[str])
        """
        user = self._user_provider()
        if not user:
            return False, "Kein Benutzer angemeldet."

        record = self._repo.get(doc_id)
        if not record:
            return False, "Dokument nicht gefunden."

        # Get allowed transitions
        allowed_actions = self._wf_policy. allowed_transitions(record.status)
        if not allowed_actions:
            return False, "Keine zulässige Aktion verfügbar."

        # Take first allowed action
        next_action = allowed_actions[0]

        # Check permission
        all_roles = set(user_roles) | set(assigned_roles)
        if not self._perm_policy.can_perform(action_id=next_action, roles=all_roles):
            return False, f"Keine Berechtigung für Aktion '{next_action}'."

        # Check separation of duties
        user_id = self._get_user_id(user)
        owner_id = self._repo.get_owner(doc_id)

        if self._perm_policy.violates_separation_of_duties(
            action_id=next_action,
            actor_id=user_id or "",
            owner_id=owner_id or "",
            doc_type=record.doc_type
        ):
            return False, "Verstoß gegen Funktionstrennung (z.B. Selbstfreigabe nicht erlaubt)."

        # Check if signature required
        requires_signature = self._wf_policy.requires_signature(next_action, record.doc_type)

        if requires_signature:
            # Generate PDF
            pdf_path = self._repo.generate_review_pdf(doc_id)
            if not pdf_path:
                return False, "PDF-Generierung fehlgeschlagen."

            # Sign PDF (via callback)
            if sign_pdf_callback and callable(sign_pdf_callback):
                signed_path = sign_pdf_callback(pdf_path, reason)
                if not signed_path:
                    return False, "Signierung abgebrochen."

                # Attach signed PDF
                ok, msg = self._repo.attach_signed_pdf(doc_id, signed_path, next_action, user_id or "", reason)
                if not ok:
                    return False, msg or "Signierte PDF konnte nicht angehängt werden."

        # Determine next status
        next_status = self._wf_policy.next_status(action_id=next_action, status=record.status)
        if not next_status:
            return False, f"Kein Zielstatus für Aktion '{next_action}' definiert."

        # Update status
        try:
            self._repo.set_status(doc_id, next_status, user_id or "", reason)

            # Bump version if publishing
            if next_status == DocumentStatus.EFFECTIVE:
                self._repo.bump_minor_version(doc_id, user_id or "", reason)
                # Export versioned PDF
                self._repo.export_pdf_with_version_suffix(doc_id)

            return True, None
        except Exception as ex:
            return False, f"Status-Update fehlgeschlagen: {ex}"

    def backward_to_draft(
        self,
        doc_id: str,
        reason: str,
        *,
        user_roles: list[str]
    ) -> Tuple[bool, Optional[str]]:
        """
        Revert document to DRAFT.

        Args:
            doc_id: Document ID
            reason: Reason
            user_roles: User's roles

        Returns:
            (success:  bool, error_msg: Optional[str])
        """
        user = self._user_provider()
        if not user:
            return False, "Kein Benutzer angemeldet."

        if not self._perm_policy. can_perform(action_id="back_to_draft", roles=user_roles):
            return False, "Keine Berechtigung."

        try:
            user_id = self._get_user_id(user)
            self._repo.set_status(doc_id, DocumentStatus.DRAFT, user_id or "", reason)
            return True, None
        except Exception as ex:
            return False, f"Zurücksetzen fehlgeschlagen:  {ex}"

    def archive(
        self,
        doc_id: str,
        reason: str,
        *,
        user_roles: list[str]
    ) -> Tuple[bool, Optional[str]]:
        """
        Archive document.

        Args:
            doc_id: Document ID
            reason: Reason
            user_roles: User's roles

        Returns:
            (success: bool, error_msg: Optional[str])
        """
        user = self._user_provider()
        if not user:
            return False, "Kein Benutzer angemeldet."

        record = self._repo.get(doc_id)
        if not record:
            return False, "Dokument nicht gefunden."

        # Determine action based on current status
        if record.status == DocumentStatus.EFFECTIVE:
            action_id = "obsolete"
            target_status = DocumentStatus.OBSOLETE
        elif record.status == DocumentStatus. OBSOLETE:
            action_id = "archive"
            target_status = DocumentStatus.ARCHIVED
        else:
            return False, "Nur gültige oder obsolete Dokumente können archiviert werden."

        # Check permission
        if not self._perm_policy.can_perform(action_id=action_id, roles=user_roles):
            return False, "Keine Berechtigung."

        try:
            user_id = self._get_user_id(user)
            self._repo.set_status(doc_id, target_status, user_id or "", reason)
            return True, None
        except Exception as ex:
            return False, f"Archivierung fehlgeschlagen: {ex}"

    def _get_user_id(self, user: object) -> Optional[str]:
        """Extract user ID."""
        for attr in ("id", "user_id", "uid"):
            val = getattr(user, attr, None)
            if val:
                return str(val)
        return None