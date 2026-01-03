"""WorkflowController - orchestrates workflow transitions with signature support."""

from __future__ import annotations
import logging
import os
import tempfile
from typing import Callable, List, Optional, Tuple, Any
from documents.services.policy.permission_policy import AccessContext
from documents.enum.document_status import DocumentStatus
logger = logging.getLogger(__name__)


class WorkflowController:
    """Orchestrates workflow transitions with signature support."""

    def __init__(
        self,
        *,
        repository,
        workflow_policy,
        permission_policy,
        current_user_provider: Callable[[], Optional[object]],
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
        """Start workflow.

        Note:
            Permission checks are centralized in PermissionPolicy.can_execute().
        """
        user = self._user_provider()
        if not user:
            return False, "Kein Benutzer angemeldet."

        record = self._repo.get(doc_id)
        if not record:
            return False, "Dokument nicht gefunden."

        if self._repo.is_workflow_active(doc_id):
            return False, "Workflow ist bereits aktiv."

        user_id = self._get_user_id(user)
        owner_id = self._repo.get_owner(doc_id)

        # Central policy check (owner/status constraint handled in policy)
        ok, reason = self._perm_policy.can_execute(
            action_id="start_workflow",
            ctx=AccessContext(
                actor_id=user_id or "",
                owner_id=owner_id,
                status=self._to_status_name(record.status),
                doc_type=str(record.doc_type),
                assigned_roles=tuple((assigned_roles or [])),
                system_roles=tuple((user_roles or [])),
                signatures=tuple(),
            ),
        )
        if not ok:
            return False, reason or "Keine Berechtigung."

        # Ensure assignments exist if requested (UI hook)
        if ensure_assignments_callback and callable(ensure_assignments_callback):
            try:
                ensured_ok = bool(ensure_assignments_callback())
            except Exception as ex:
                logger.error(f"Ensure assignments callback failed: {ex}")
                ensured_ok = False
            if not ensured_ok:
                return False, "Zuweisungen sind unvollständig."

        try:
            self._repo.set_workflow_active(doc_id, True, started_by=user_id or "")
            logger.info(f"Workflow started for {doc_id} by {user_id}")
            return True, None
        except Exception as ex:
            logger.error(f"Workflow start failed: {ex}")
            return False, str(ex)

    def abort_workflow(
        self,
        doc_id: str,
        reason: str,
        *,
        user_roles: List[str],
        assigned_roles: Optional[List[str]] = None
    ) -> Tuple[bool, Optional[str]]:
        """Abort workflow (administrative action)."""
        user = self._user_provider()
        if not user:
            return False, "Kein Benutzer angemeldet."

        record = self._repo.get(doc_id)
        if not record:
            return False, "Dokument nicht gefunden."

        if not self._repo.is_workflow_active(doc_id):
            return False, "Workflow ist nicht aktiv."

        user_id = self._get_user_id(user)
        owner_id = self._repo.get_owner(doc_id)

        ok, deny_reason = self._perm_policy.can_execute(
            action_id="abort_workflow",
            ctx=AccessContext(
                actor_id=user_id or "",
                owner_id=owner_id,
                status=self._to_status_name(record.status),
                doc_type=str(record.doc_type),
                assigned_roles=tuple((assigned_roles or [])),
                system_roles=tuple((user_roles or [])),
                signatures=tuple(self._repo.list_signatures(doc_id) or []),
            ),
        )
        if not ok:
            return False, deny_reason or "Keine Berechtigung."

        if self._wf_policy.requires_reason("abort_workflow"):
            if not reason or not reason.strip():
                return False, "Begründung erforderlich für diese Aktion."

        try:
            self._repo.set_workflow_active(doc_id, False, started_by="")
            logger.info(f"Workflow aborted for {doc_id} by {user_id} ({reason})")
            return True, None
        except Exception as ex:
            logger.error(f"Workflow abort failed: {ex}")
            return False, str(ex)

    def forward_transition(
        self,
        doc_id: str,
        reason: str,
        *,
        user_roles: List[str],
        assigned_roles: List[str],
        sign_pdf_callback: Optional[Callable[[str, str], Optional[str]]] = None
    ) -> Tuple[bool, Optional[str]]:
        """Execute next workflow step with signature support."""
        user = self._user_provider()
        if not user:
            return False, "Kein Benutzer angemeldet."

        record = self._repo.get(doc_id)
        if not record:
            return False, "Dokument nicht gefunden."

        allowed_actions = self._wf_policy.allowed_transitions(record.status)
        if not allowed_actions:
            status_name = self._to_status_name(record.status)
            return False, f"Keine Aktion möglich für Status '{status_name}'."

        user_id = self._get_user_id(user)
        owner_id = self._repo.get_owner(doc_id)
        signatures = tuple(self._repo.list_signatures(doc_id) or [])

        # Determine first permitted action in the current status
        permitted_action: Optional[str] = None
        deny_reason: Optional[str] = None

        for action in allowed_actions:
            ok, r = self._perm_policy.can_execute(
                action_id=action,
                ctx=AccessContext(
                    actor_id=user_id or "",
                    owner_id=owner_id,
                    status=self._to_status_name(record.status),
                    doc_type=str(record.doc_type),
                    assigned_roles=tuple((assigned_roles or [])),
                    system_roles=tuple((user_roles or [])),
                    signatures=signatures,
                ),
            )
            if ok:
                permitted_action = action
                break
            deny_reason = r or deny_reason

        if not permitted_action:
            return False, deny_reason or "Keine Berechtigung für verfügbare Aktionen."

        if self._wf_policy.requires_reason(permitted_action):
            if not reason or not reason.strip():
                return False, "Begründung erforderlich für diese Aktion."

# Determine target status early (needed for signing artifact rules)
        next_status_name = self._wf_policy.next_status(
            action_id=permitted_action,
            status=record.status
        )
        if not next_status_name:
            return False, f"Kein Zielstatus für Aktion '{permitted_action}' definiert."

        # Convert DOCX->PDF only on DRAFT -> REVIEW transition
        is_draft_to_review = (
            self._to_status_name(record.status) == "DRAFT"
            and str(next_status_name).upper() == "REVIEW"
        )

        # Check if signature required
        requires_sig = self._wf_policy.requires_signature(permitted_action, record.doc_type)

        if requires_sig:
            # Generate/get PDF for signing
            pdf_path = self._generate_pdf_for_signing(doc_id, record, is_draft_to_review)

            if not pdf_path:
                return False, "PDF-Generierung für Signierung fehlgeschlagen."

            signed_path = None
            if sign_pdf_callback and callable(sign_pdf_callback):
                try:
                    signed_path = sign_pdf_callback(pdf_path, reason or "")
                except Exception as ex:
                    logger.error(f"Signature callback failed: {ex}")
                    return False, f"Signierung fehlgeschlagen: {ex}"

            if not signed_path:
                return False, "Signierung abgebrochen oder fehlgeschlagen."

            # Persist current signing PDF (single source of truth)
            try:
                self._repo.set_signing_pdf(doc_id, signed_path)
            except Exception as ex:
                logger.error(f"Failed to persist signing PDF path: {ex}")
                return False, f"Signiertes PDF konnte nicht persistiert werden: {ex}"

            # Attach signed PDF (metadata)
            try:
                success, msg = self._repo.attach_signed_pdf(
                    doc_id, signed_path, permitted_action, user_id or "", reason or ""
                )
                if not success:
                    return False, msg or "Signierte PDF konnte nicht angehängt werden."
            except Exception as ex:
                logger.error(f"Attach signed PDF failed: {ex}")
                return False, f"Signierte PDF konnte nicht gespeichert werden: {ex}"

        try:
            from documents.enum.document_status import DocumentStatus

            # Set new status
            self._repo.set_status(
                doc_id,
                DocumentStatus[str(next_status_name).upper()],
                user_id or "",
                reason or ""
            )

            if str(next_status_name).upper() == "EFFECTIVE":
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
        """Backward transition to draft (administrative action)."""
        user = self._user_provider()
        if not user:
            return False, "Kein Benutzer angemeldet."
        if not reason or not reason.strip():
            return False, "Begründung erforderlich."

        record = self._repo.get(doc_id)
        if not record:
            return False, "Dokument nicht gefunden."

        user_id = self._get_user_id(user)
        owner_id = self._repo.get_owner(doc_id)

        ok, deny_reason = self._perm_policy.can_execute(
            action_id="back_to_draft",
            ctx=AccessContext(
                actor_id=user_id or "",
                owner_id=owner_id,
                status=self._to_status_name(record.status),
                doc_type=str(record.doc_type),
                assigned_roles=tuple((assigned_roles or [])),
                system_roles=tuple((user_roles or [])),
                signatures=tuple(self._repo.list_signatures(doc_id) or []),
            ),
        )
        if not ok:
            return False, deny_reason or "Keine Berechtigung."

        try:
            # Reset status and workflow
            self._repo.set_status(doc_id, DocumentStatus.DRAFT, user_id or "", reason)
            self._repo.set_workflow_active(doc_id, False, started_by="")
            logger.info(f"Back to draft for {doc_id} by {user_id} ({reason})")
            return True, None
        except Exception as ex:
            logger.error(f"Back to draft failed: {ex}")
            return False, str(ex)

    def _generate_pdf_for_signing(self, doc_id: str, record, is_draft_to_review: bool) -> Optional[str]:
        """
        Generate or get PDF for signing.

        Rules:
        - Convert DOCX to PDF ONLY if transitioning from DRAFT to REVIEW.
        - Otherwise ALWAYS reuse the current signing PDF stored in the repository.
        """
        # Always reuse existing signing PDF (single source of truth)
        signing_pdf_path = self._repo.get_signing_pdf(doc_id)
        if signing_pdf_path and os.path.isfile(signing_pdf_path):
            logger.debug(f"Using existing signing PDF: {signing_pdf_path}")
            return signing_pdf_path

        # Only convert DOCX->PDF on DRAFT->REVIEW
        if not is_draft_to_review:
            logger.debug("No conversion allowed: not a DRAFT->REVIEW transition and no signing PDF exists.")
            return None

        file_path = getattr(record, "current_file_path", None)
        if not file_path or not os.path.isfile(file_path):
            logger.error(f"No valid file path for document {doc_id}")
            return None

        if not file_path.lower().endswith((".doc", ".docx")):
            logger.error("File is not a DOCX and cannot be converted.")
            return None

        try:
            from documents.logic.doc_convert import convert_to_pdf
            temp_dir = tempfile.gettempdir()
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            pdf_output = os.path.join(temp_dir, f"{base_name}_{doc_id}_review.pdf")
            result = convert_to_pdf(file_path, pdf_output)
            if result and os.path.isfile(result):
                logger.info(f"Converted DOCX to PDF: {result}")
                return result
        except Exception as ex:
            logger.error(f"DOCX to PDF conversion failed: {ex}")

        return None

    @staticmethod
    def _get_user_id(user: object) -> Optional[str]:
        """Try to read user identifier from user object."""
        for attr in ("user_id", "id", "username", "name"):
            val = getattr(user, attr, None)
            if val:
                return str(val)
        return None

    @staticmethod
    def _to_status_name(status: Any) -> str:
        """Normalize status to canonical name."""
        if status is None:
            return ""
        if hasattr(status, "name"):
            return str(status.name).upper()
        if hasattr(status, "value"):
            return str(status.value).upper()
        return str(status).upper()
