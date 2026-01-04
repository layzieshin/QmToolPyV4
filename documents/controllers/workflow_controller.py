"""WorkflowController - orchestrates workflow transitions with signature support."""

from __future__ import annotations
import logging
import os
import tempfile
import shutil
from pathlib import Path
from typing import Callable, List, Optional, Tuple, Any

from documents.logic.lifecycle_paths import ArtifactType, LifecyclePathResolver, LifecycleRoots
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
        """Abort workflow (administrative action).

        Phase 3 behavior:
        - Clears the signing PDF reference.
        - Resets current_file_path back to the DOCX working copy (fallback) to support abort rollback.
        """
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
            # Clear signing PDF reference first
            try:
                self._repo.clear_signing_pdf(doc_id)
            except Exception as ex:
                logger.warning(f"Failed to clear signing PDF on abort: {ex}")

            # Reset current file path to DOCX working copy (best effort)
            docx_path = self._resolve_docx_working_copy_path(record)
            if docx_path and os.path.isfile(docx_path):
                self._persist_current_file_path(doc_id, docx_path)

            # Reset workflow flag
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
        """Execute next workflow step with signature support.

        Phase 3 behavior:
        - On DRAFT -> REVIEW: converts DOCX working copy into lifecycle PDF working copy and switches current_file_path to PDF.
        - During signing rounds: always signs the lifecycle PDF working copy (single source of truth).
        - Does NOT apply final '_signed' naming here; that is handled at final publishing/export (copy_to_destination).

        Phase 4 behavior:
        - On OBSOLETE -> ARCHIVED: move the entire lifecycle version folder to LifeCycle/Archive/... and update paths.
        """
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

        next_status_name = self._wf_policy.next_status(
            action_id=permitted_action,
            status=record.status
        )
        if not next_status_name:
            return False, f"Kein Zielstatus für Aktion '{permitted_action}' definiert."

        is_draft_to_review = (
            self._to_status_name(record.status) == "DRAFT"
            and str(next_status_name).upper() == "REVIEW"
        )

        requires_sig = self._wf_policy.requires_signature(permitted_action, record.doc_type)

        if requires_sig:
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

            canonical_pdf_path = self._resolve_pdf_working_copy_path(record) or pdf_path
            try:
                if os.path.abspath(signed_path) != os.path.abspath(canonical_pdf_path):
                    Path(canonical_pdf_path).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(signed_path, canonical_pdf_path)

                    # Clean up temp signed output (best effort)
                    try:
                        if os.path.isfile(signed_path) and os.path.dirname(os.path.abspath(signed_path)) == os.path.dirname(os.path.abspath(canonical_pdf_path)):
                            os.remove(signed_path)
                    except Exception:
                        pass
                else:
                    canonical_pdf_path = signed_path
            except Exception as ex:
                logger.error(f"Failed to store signed PDF into lifecycle working copy: {ex}")
                return False, f"Signierte PDF konnte nicht gespeichert werden: {ex}"

            try:
                self._repo.set_signing_pdf(doc_id, canonical_pdf_path)
            except Exception as ex:
                logger.error(f"Failed to persist signing PDF path: {ex}")
                return False, f"Signiertes PDF konnte nicht persistiert werden: {ex}"

            self._persist_current_file_path(doc_id, canonical_pdf_path)

            try:
                success, msg = self._repo.attach_signed_pdf(
                    doc_id, canonical_pdf_path, permitted_action, user_id or "", reason or ""
                )
                if not success:
                    return False, msg or "Signierte PDF konnte nicht angehängt werden."
            except Exception as ex:
                logger.error(f"Attach signed PDF failed: {ex}")
                return False, f"Signierte PDF konnte nicht angehängt werden: {ex}"

        # Persist status change
        try:
            self._repo.set_status(
                doc_id,
                DocumentStatus[str(next_status_name).upper()],
                user_id or "",
                reason or ""
            )

            # Minor bump only when EFFECTIVE (existing behavior)
            if str(next_status_name).upper() == "EFFECTIVE":
                self._repo.bump_minor_version(doc_id, user_id or "", reason)

            # Phase 4: If ARCHIVED, move version folder into LifeCycle/Archive and update paths
            if str(next_status_name).upper() == "ARCHIVED":
                try:
                    self._archive_current_version_folder(doc_id, record)
                except Exception as ex:
                    logger.error(f"Archive move failed: {ex}")
                    return False, f"Archivierung fehlgeschlagen: {ex}"

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
        """Backward transition to draft (administrative action).

        Phase 3 behavior:
        - Clears signing PDF reference.
        - Resets current_file_path to the DOCX working copy.
        """
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
            action_id="backward_to_draft",
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

            # Clear signing PDF reference and restore DOCX as current file
            try:
                self._repo.clear_signing_pdf(doc_id)
            except Exception as ex:
                logger.warning(f"Failed to clear signing PDF on backward_to_draft: {ex}")

            docx_path = self._resolve_docx_working_copy_path(record)
            if docx_path and os.path.isfile(docx_path):
                self._persist_current_file_path(doc_id, docx_path)

            logger.info(f"Back to draft for {doc_id} by {user_id} ({reason})")
            return True, None
        except Exception as ex:
            logger.error(f"Back to draft failed: {ex}")
            return False, str(ex)

    def _generate_pdf_for_signing(self, doc_id: str, record, is_draft_to_review: bool) -> Optional[str]:
        """
        Generate or get PDF for signing.

        Phase 3 behavior:
        - Signing always uses the lifecycle PDF working copy:
              ./documents/LifeCycle/<CODE>/V<version>/<CODE>_<TITLE>_v<version>.pdf
        - Convert DOCX to PDF ONLY if transitioning from DRAFT to REVIEW.
        - Otherwise ALWAYS reuse the current signing PDF stored in the repository.
        - If a repository signing PDF exists but is outside the lifecycle folder, we copy it into the lifecycle path
          (single source of truth) and persist the lifecycle path.
        """
        # Prefer existing signing PDF reference (single source of truth)
        signing_pdf_path = self._repo.get_signing_pdf(doc_id)
        lifecycle_pdf_path = self._resolve_pdf_working_copy_path(record)

        if signing_pdf_path and os.path.isfile(signing_pdf_path):
            # If we already have a lifecycle path, enforce it as the canonical location.
            if lifecycle_pdf_path:
                try:
                    # If the existing signing pdf is already the lifecycle path, reuse directly.
                    if os.path.abspath(signing_pdf_path) != os.path.abspath(lifecycle_pdf_path):
                        Path(lifecycle_pdf_path).parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(signing_pdf_path, lifecycle_pdf_path)
                    # Persist canonical lifecycle path and make it current
                    self._repo.set_signing_pdf(doc_id, lifecycle_pdf_path)
                    self._persist_current_file_path(doc_id, lifecycle_pdf_path)
                    logger.debug(f"Using canonical lifecycle signing PDF: {lifecycle_pdf_path}")
                    return lifecycle_pdf_path
                except Exception as ex:
                    logger.warning(f"Failed to canonicalize signing PDF into lifecycle path: {ex}")
                    # fallback to original
                    logger.debug(f"Using existing signing PDF (non-canonical): {signing_pdf_path}")
                    return signing_pdf_path

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

            if not lifecycle_pdf_path:
                # Fallback: temp dir if we cannot resolve lifecycle path (should not happen with proper metadata).
                temp_dir = tempfile.gettempdir()
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                lifecycle_pdf_path = os.path.join(temp_dir, f"{base_name}_{doc_id}_review.pdf")

            Path(lifecycle_pdf_path).parent.mkdir(parents=True, exist_ok=True)
            result = convert_to_pdf(file_path, lifecycle_pdf_path)
            if result and os.path.isfile(result):
                logger.info(f"Converted DOCX to PDF: {result}")

                # Persist canonical signing PDF and make it the current open target
                try:
                    self._repo.set_signing_pdf(doc_id, result)
                except Exception as ex:
                    logger.warning(f"Failed to persist signing PDF path after conversion: {ex}")

                self._persist_current_file_path(doc_id, result)
                return result
        except Exception as ex:
            logger.error(f"DOCX to PDF conversion failed: {ex}")

        return None

    # ---------------------------------------------------------------------
    # Lifecycle helpers (Phase 3)
    # ---------------------------------------------------------------------
    def _archive_current_version_folder(self, doc_id: str, record: object) -> None:
        """Move the entire lifecycle version directory into LifeCycle/Archive and update DB paths.

        Target:
            ./documents/LifeCycle/Archive/<CODE>/V<version>/

        Notes:
        - We move the directory (DOCX + PDF + any artifacts) as a unit.
        - After move, we update:
            - current_file_path (to the moved file equivalent)
            - signing_pdf_path (if present)
        """
        resolver = LifecyclePathResolver(LifecycleRoots.from_cwd())

        code = self._resolve_document_code(record)
        if not code:
            raise ValueError("Dokumentenkennung (doc_code) fehlt – Archivpfad kann nicht ermittelt werden.")

        version = getattr(record, "version_label", None) or f"{getattr(record, 'version_major', 1)}.{getattr(record, 'version_minor', 0)}"
        src_dir = resolver.version_dir(document_code=code, version=str(version), archived=False)
        dst_dir = resolver.version_dir(document_code=code, version=str(version), archived=True)

        if not src_dir.exists():
            raise FileNotFoundError(str(src_dir))

        dst_dir.parent.mkdir(parents=True, exist_ok=True)

        # If destination exists, create a non-destructive alternative
        final_dst = dst_dir
        if final_dst.exists():
            for i in range(2, 1000):
                candidate = Path(str(dst_dir) + f"_dup{i}")
                if not candidate.exists():
                    final_dst = candidate
                    break

        shutil.move(str(src_dir), str(final_dst))

        # Update paths in DB to point to new location (keep basenames)
        moved_current = None
        cur = getattr(record, "current_file_path", None)
        if cur:
            moved_current = str(final_dst / Path(cur).name)

        moved_signing = None
        try:
            signing = self._repo.get_signing_pdf(doc_id)
        except Exception:
            signing = None
        if signing:
            moved_signing = str(final_dst / Path(signing).name)

        if moved_signing and os.path.isfile(moved_signing):
            # keep signing_pdf_path consistent
            if hasattr(self._repo, "set_signing_pdf_path_only"):
                self._repo.set_signing_pdf_path_only(doc_id, moved_signing)
            # current file should also point to the best artifact (PDF preferred)
            self._persist_current_file_path(doc_id, moved_signing)
        elif moved_current and os.path.isfile(moved_current):
            self._persist_current_file_path(doc_id, moved_current)



    def _persist_current_file_path(self, doc_id: str, path: str) -> None:
        """Persist the current file path for a document (single open target).

        We keep this as a best-effort method to avoid hard coupling to a specific repository implementation.
        Preferred: repository.set_current_file_path(doc_id, path)

        If not available, we try repository.update_metadata(...), but this requires the repository to accept
        'current_file_path' as an updateable field.
        """
        if not path:
            return
        try:
            if hasattr(self._repo, "set_current_file_path") and callable(getattr(self._repo, "set_current_file_path")):
                self._repo.set_current_file_path(doc_id, path)
                return
        except Exception as ex:
            logger.warning(f"set_current_file_path failed: {ex}")

        try:
            if hasattr(self._repo, "update_metadata") and callable(getattr(self._repo, "update_metadata")):
                # type: ignore[call-arg]
                self._repo.update_metadata({"doc_id": doc_id, "current_file_path": path}, user_id="")
        except Exception as ex:
            logger.warning(f"update_metadata(current_file_path) failed: {ex}")

    def _resolve_docx_working_copy_path(self, record) -> Optional[str]:
        """Resolve the lifecycle DOCX working copy path for the given record."""
        try:
            resolver = LifecyclePathResolver(LifecycleRoots.from_cwd())
            code = self._resolve_document_code(record)
            if not code:
                return None
            version = getattr(record, "version_label", None) or f"{getattr(record, 'version_major', 1)}.{getattr(record, 'version_minor', 0)}"
            title = getattr(record, "title", None)
            path = resolver.artifact_path(
                document_code=code,
                version=str(version),
                title=title,
                artifact=ArtifactType.DOCX,
                archived=False,
            )
            return str(path)
        except Exception:
            return None

    def _resolve_pdf_working_copy_path(self, record) -> Optional[str]:
        """Resolve the lifecycle PDF working copy path for the given record."""
        try:
            resolver = LifecyclePathResolver(LifecycleRoots.from_cwd())
            code = self._resolve_document_code(record)
            if not code:
                return None
            version = getattr(record, "version_label", None) or f"{getattr(record, 'version_major', 1)}.{getattr(record, 'version_minor', 0)}"
            title = getattr(record, "title", None)
            path = resolver.artifact_path(
                document_code=code,
                version=str(version),
                title=title,
                artifact=ArtifactType.PDF,
                archived=False,
            )
            return str(path)
        except Exception:
            return None

    def _resolve_document_code(self, record) -> Optional[str]:
        """Get document code from record or derive from current_file_path."""
        code = getattr(record, "doc_code", None)
        if code:
            try:
                resolver = LifecyclePathResolver(LifecycleRoots.from_cwd())
                return resolver.normalize_document_code(code)
            except Exception:
                return str(code).strip().upper() if str(code).strip() else None

        file_path = getattr(record, "current_file_path", None)
        if file_path:
            try:
                resolver = LifecyclePathResolver(LifecycleRoots.from_cwd())
                return resolver.parse_document_code_from_filename(str(file_path))
            except Exception:
                return None
        return None

    @staticmethod
    def _get_user_id(user: object) -> Optional[str]:
        """Extract user id from common user object shapes."""
        for attr in ("id", "user_id", "uid", "username", "name"):
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
