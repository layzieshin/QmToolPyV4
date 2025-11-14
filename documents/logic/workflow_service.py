# documents/logic/workflow_service.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Iterable, Set, Dict, List

try:
    from documents.models.document_models import DocumentStatus
except Exception as ex:
    raise ImportError("documents.models.document_models.DocumentStatus is required") from ex


@dataclass(frozen=True)
class TransitionResult:
    success: bool
    message: str = ""
    new_status: Optional[DocumentStatus] = None


class WorkflowService:
    """
    Orchestrates lifecycle transitions, considering both:
    - global roles (ADMIN/QMB/AUTHOR/REVIEWER/APPROVER)
    - per-document assignments (assignees['AUTHOR'/'REVIEWER'/'APPROVER'])

    Public guard methods (used by GUI):
        can_submit_to_review(...)
        can_request_approval(...)
        can_publish(...)
        can_back_to_draft(...)

    The guards accept only roles+status (backward compatible),
    but if you also pass doc_id and actor/user_id they will include
    per-document assignments for a more accurate decision.
    """

    def __init__(self, *, repository, permissions) -> None:
        self._repo = repository
        self._perm = permissions

        must = ["get", "generate_review_pdf", "export_pdf_with_version_suffix",
                "attach_signed_pdf", "set_status", "get_assignees"]
        missing = [m for m in must if not hasattr(self._repo, m)]
        if missing:
            raise AttributeError(f"Repository missing required methods: {', '.join(missing)}")
        if not hasattr(self._perm, "roles_for_user"):
            raise AttributeError("Permissions must implement roles_for_user(user)->set[str].")

    # ---- helpers ------------------------------------------------------------

    @staticmethod
    def _user_id_of(actor: object | None) -> str:
        if not actor:
            return ""
        for attr in ("id", "user_id", "email", "name", "username"):
            v = getattr(actor, attr, None)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""

    def roles_of(self, user: object | None) -> Set[str]:
        try:
            return {str(r).upper() for r in (self._perm.roles_for_user(user) or set())}
        except Exception:
            return set()

    @staticmethod
    def _has_any(roles: Iterable[str], required: Iterable[str]) -> bool:
        rs = {str(r).upper() for r in roles}
        rq = {str(r).upper() for r in required}
        return bool(rs & rq)

    def _assigned_roles(self, doc_id: str, user_id: str) -> Set[str]:
        try:
            ass: Dict[str, List[str]] = self._repo.get_assignees(doc_id) or {}
        except Exception:
            return set()
        result: Set[str] = set()
        uid = (user_id or "").strip().lower()
        if not uid:
            return set()
        for role, users in ass.items():
            if not users:
                continue
            if any((str(u).strip().lower() == uid) for u in users):
                result.add(role.upper())
        return result

    def _ensure_author_assigned(self, doc_id: str, user_id: str) -> None:
        """If no AUTHOR is assigned yet, assign the current user as AUTHOR (best effort)."""
        try:
            ass = self._repo.get_assignees(doc_id) or {}
            authors = ass.get("AUTHOR") or []
            if authors:
                return
            if hasattr(self._repo, "set_assignees"):
                self._repo.set_assignees(
                    doc_id,
                    authors=[user_id],
                    reviewers=ass.get("REVIEWER") or None,
                    approvers=ass.get("APPROVER") or None,
                )
        except Exception:
            pass  # soft-fail

    # ---- internal guards (need assigned roles) ------------------------------

    def _can_submit_to_review(self, *, roles: Set[str], assigned: Set[str], status: DocumentStatus) -> bool:
        return status == DocumentStatus.DRAFT and (
            self._has_any(roles, {"AUTHOR", "QMB", "ADMIN"}) or ("AUTHOR" in assigned)
        )

    def _can_request_approval(self, *, roles: Set[str], assigned: Set[str], status: DocumentStatus) -> bool:
        return status == DocumentStatus.IN_REVIEW and (
            self._has_any(roles, {"REVIEWER", "QMB", "ADMIN"}) or ("REVIEWER" in assigned)
        )

    def _can_publish(self, *, roles: Set[str], assigned: Set[str], status: DocumentStatus) -> bool:
        return status == DocumentStatus.APPROVAL and (
            self._has_any(roles, {"APPROVER", "QMB", "ADMIN"}) or ("APPROVER" in assigned)
        )

    # ---- PUBLIC guards (used by GUI; doc_id/actor optional) -----------------

    def can_submit_to_review(
        self,
        *,
        roles: Set[str],
        status: DocumentStatus,
        doc_id: Optional[str] = None,
        actor: object | None = None,
        user_id: Optional[str] = None,
    ) -> bool:
        assigned: Set[str] = set()
        if doc_id:
            aid = user_id or self._user_id_of(actor)
            if aid:
                assigned = self._assigned_roles(doc_id, aid)
        return self._can_submit_to_review(roles=roles, assigned=assigned, status=status)

    def can_request_approval(
        self,
        *,
        roles: Set[str],
        status: DocumentStatus,
        doc_id: Optional[str] = None,
        actor: object | None = None,
        user_id: Optional[str] = None,
    ) -> bool:
        assigned: Set[str] = set()
        if doc_id:
            aid = user_id or self._user_id_of(actor)
            if aid:
                assigned = self._assigned_roles(doc_id, aid)
        return self._can_request_approval(roles=roles, assigned=assigned, status=status)

    def can_publish(
        self,
        *,
        roles: Set[str],
        status: DocumentStatus,
        doc_id: Optional[str] = None,
        actor: object | None = None,
        user_id: Optional[str] = None,
    ) -> bool:
        assigned: Set[str] = set()
        if doc_id:
            aid = user_id or self._user_id_of(actor)
            if aid:
                assigned = self._assigned_roles(doc_id, aid)
        return self._can_publish(roles=roles, assigned=assigned, status=status)

    def can_back_to_draft(self, *, roles: Set[str], status: DocumentStatus) -> bool:
        return status != DocumentStatus.DRAFT and self._has_any(
            roles, {"AUTHOR", "REVIEWER", "APPROVER", "QMB", "ADMIN"}
        )

    # ---- actions ------------------------------------------------------------

    def submit_to_review(self, *, doc_id: str, actor: object | None,
                         user_id: str, reason: str, signed_pdf_path: str) -> TransitionResult:
        if not doc_id:
            return TransitionResult(False, "doc_id is required.")
        rec = self._repo.get(doc_id)
        if not rec:
            return TransitionResult(False, "Document not found.")
        if not isinstance(reason, str) or not reason.strip():
            return TransitionResult(False, "Reason is required.")

        actor_id = user_id or self._user_id_of(actor)
        roles = self.roles_of(actor)
        # Make sure we have an AUTHOR if none set (fresh import)
        self._ensure_author_assigned(doc_id, actor_id)
        assigned = self._assigned_roles(doc_id, actor_id)

        if not self._can_submit_to_review(roles=roles, assigned=assigned, status=rec.status):
            return TransitionResult(False, "Not allowed to submit to review.")

        pdf = self._repo.generate_review_pdf(doc_id)
        if not (pdf and isinstance(pdf, str)):
            return TransitionResult(False, "Could not generate review PDF.")
        if not (signed_pdf_path and isinstance(signed_pdf_path, str)):
            return TransitionResult(False, "Signed PDF is missing.")

        if not self._repo.attach_signed_pdf(doc_id, signed_pdf_path, "submit_review", actor_id, reason):
            return TransitionResult(False, "Could not attach signed PDF for review.")

        self._repo.set_status(doc_id, DocumentStatus.IN_REVIEW, actor_id, reason)
        return TransitionResult(True, "Submitted to review.", DocumentStatus.IN_REVIEW)

    def request_approval(self, *, doc_id: str, actor: object | None,
                         user_id: str, reason: str, signed_pdf_path: str) -> TransitionResult:
        if not doc_id:
            return TransitionResult(False, "doc_id is required.")
        rec = self._repo.get(doc_id)
        if not rec:
            return TransitionResult(False, "Document not found.")
        if not isinstance(reason, str) or not reason.strip():
            return TransitionResult(False, "Reason is required.")
        actor_id = user_id or self._user_id_of(actor)
        roles = self.roles_of(actor)
        assigned = self._assigned_roles(doc_id, actor_id)

        if not self._can_request_approval(roles=roles, assigned=assigned, status=rec.status):
            return TransitionResult(False, "Not allowed to request approval.")
        if not (signed_pdf_path and isinstance(signed_pdf_path, str)):
            return TransitionResult(False, "Signed PDF is missing.")

        if not self._repo.attach_signed_pdf(doc_id, signed_pdf_path, "request_approval", actor_id, reason):
            return TransitionResult(False, "Could not attach signed PDF for approval.")

        self._repo.set_status(doc_id, DocumentStatus.APPROVAL, actor_id, reason)
        return TransitionResult(True, "Moved to approval.", DocumentStatus.APPROVAL)

    def publish(self, *, doc_id: str, actor: object | None,
                user_id: str, reason: str, signed_pdf_path: str) -> TransitionResult:
        if not doc_id:
            return TransitionResult(False, "doc_id is required.")
        rec = self._repo.get(doc_id)
        if not rec:
            return TransitionResult(False, "Document not found.")
        if not isinstance(reason, str) or not reason.strip():
            return TransitionResult(False, "Reason is required.")
        actor_id = user_id or self._user_id_of(actor)
        roles = self.roles_of(actor)
        assigned = self._assigned_roles(doc_id, actor_id)

        if not self._can_publish(roles=roles, assigned=assigned, status=rec.status):
            return TransitionResult(False, "Not allowed to publish.")

        pub_pdf = self._repo.export_pdf_with_version_suffix(doc_id)
        if not (pub_pdf and isinstance(pub_pdf, str)):
            return TransitionResult(False, "Could not create versioned PDF for publishing.")
        if not (signed_pdf_path and isinstance(signed_pdf_path, str)):
            return TransitionResult(False, "Signed PDF is missing.")

        if not self._repo.attach_signed_pdf(doc_id, signed_pdf_path, "publish", actor_id, reason):
            return TransitionResult(False, "Could not attach signed PDF for publish step.")

        self._repo.set_status(doc_id, DocumentStatus.PUBLISHED, actor_id, reason)
        return TransitionResult(True, "Document published.", DocumentStatus.PUBLISHED)

    def back_to_draft(self, *, doc_id: str, actor: object | None,
                      user_id: str, reason: str) -> TransitionResult:
        if not doc_id:
            return TransitionResult(False, "doc_id is required.")
        if not (isinstance(reason, str) and reason.strip()):
            return TransitionResult(False, "Reason is required for backward transition.")

        rec = self._repo.get(doc_id)
        if not rec:
            return TransitionResult(False, "Document not found.")
        roles = self.roles_of(actor)
        if not self.can_back_to_draft(roles=roles, status=rec.status):
            return TransitionResult(False, "Not allowed to reset to draft.")

        actor_id = user_id or self._user_id_of(actor)
        self._repo.set_status(doc_id, DocumentStatus.DRAFT, actor_id, reason)

        if hasattr(self._repo, "restore_docx_after_backward"):
            try:
                self._repo.restore_docx_after_backward(doc_id)
            except Exception as ex:
                return TransitionResult(True, f"Reset to draft (DOCX auto-restore failed: {ex})", DocumentStatus.DRAFT)

        return TransitionResult(True, "Reset to draft.", DocumentStatus.DRAFT)
