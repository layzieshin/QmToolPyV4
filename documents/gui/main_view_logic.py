# documents/gui/main_view_logic.py
"""
Controller/Logic layer for the Documents main view.

This module encapsulates *all* non-UI logic so that `main_view.py` contains
only GUI code (widgets, layout, event wiring).

Updates for requirements:
- Provide actual actors (who executed steps) + signature timestamps
- Provide rich document details for the Overview (incl. DOCX meta via bridge)
- Public API to list all published documents for other modules
- Archive: move entire document folder under <root>/archived/<doc_id> and update DB paths
- Keep backward/forward workflow rules and password verification
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple
import os
import glob
import shutil
from datetime import datetime

# --- External project modules (no tkinter imports here) ----------------------
try:
    from core.common.app_context import AppContext  # type: ignore
except Exception:
    class AppContext:  # minimal shim
        current_user: object | None = None
        @staticmethod
        def signature():
            raise RuntimeError("Signature API not available")

try:
    from core.settings.logic.settings_manager import SettingsManager  # type: ignore
except Exception:
    class SettingsManager:  # type: ignore
        def get(self, section: str, key: str, default: Any = None) -> Any: return default

from documents.models.document_models import DocumentRecord, DocumentStatus  # type: ignore
from documents.logic.repository import DocumentsRepository, RepoConfig  # type: ignore
from documents.logic.workflow_engine import WorkflowEngine  # type: ignore

try:
    from documents.logic.rbac_service import RBACService  # type: ignore
except Exception:
    RBACService = None  # type: ignore

# Prefer your bridge; fall back to plain adapter if needed
try:
    from documents.logic.wordmeta_bridge import extract_core_and_comments  # type: ignore
except Exception:
    try:
        from wordmeta_bridge import extract_core_and_comments  # type: ignore
    except Exception:
        # very small fallback
        def extract_core_and_comments(path: str):
            return {}, []


@dataclass(frozen=True)
class ControlsState:
    can_open: bool
    can_copy: bool
    can_assign_roles: bool
    can_archive: bool
    can_next: bool
    can_back_to_draft: bool
    can_toggle_workflow: bool
    workflow_text: str
    next_text: str


@dataclass
class Assignments:
    authors: List[str]
    reviewers: List[str]
    approvers: List[str]


class DocumentsController:
    FEATURE_ID = "documents"

    def __init__(self, settings_manager: SettingsManager) -> None:
        self._sm = settings_manager
        self._repo: Optional[DocumentsRepository] = None
        self._rbac: Optional[RBACService] = None  # type: ignore
        self._wf = WorkflowEngine()

        self._active_cache: Dict[str, bool] = {}
        self._starter_cache: Dict[str, str] = {}
        self._last_reviewer_cache: Dict[str, str] = {}

        self._STATUS_ARCHIVED = getattr(DocumentStatus, "ARCHIVED", None)
        self._STATUS_OBSOLETE = getattr(DocumentStatus, "OBSOLETE", None)

    # --------------------------------------------------------------------- init
    def init(self) -> None:
        cfg = self._load_repo_cfg()
        self._repo = DocumentsRepository(cfg)
        if RBACService:
            rbac_db = str(self._sm.get(self.FEATURE_ID, "rbac_db_path", "") or "") \
                      or getattr(cfg, "db_path", "") or ""
            try:
                self._rbac = RBACService(rbac_db, self._sm)  # type: ignore
            except TypeError:
                try:
                    self._rbac = RBACService(self._sm)  # type: ignore
                except TypeError:
                    self._rbac = RBACService()  # type: ignore
            except Exception:
                self._rbac = None

    def _load_repo_cfg(self) -> RepoConfig:
        root = str(self._sm.get(self.FEATURE_ID, "root_path", "")) \
               or (getattr(AppContext, "app_storage_dir", None) or os.path.join(os.getcwd(), "storage"))
        db_path = str(self._sm.get(self.FEATURE_ID, "db_path", "")) or os.path.join(root, "documents.sqlite3")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        return RepoConfig(
            root_path=root,
            db_path=db_path,
            id_prefix=str(self._sm.get(self.FEATURE_ID, "id_prefix", "DOC")),
            id_pattern=str(self._sm.get(self.FEATURE_ID, "id_pattern", "{YYYY}-{seq:04d}")),
            review_months=int(self._sm.get(self.FEATURE_ID, "review_months", 24)),
            watermark_copy=str(self._sm.get(self.FEATURE_ID, "watermark_copy", "KONTROLLIERTE KOPIE")),
        )

    # ------------------------------------------------------------------- users
    @staticmethod
    def _current_user() -> Any:
        return getattr(AppContext, "current_user", None)

    @staticmethod
    def _uid_from(user: Any) -> Optional[str]:
        for attr in ("id", "user_id", "email", "username"):
            val = getattr(user, attr, None) if user else None
            if isinstance(val, str) and val.strip():
                return val.strip()
        return None

    def current_user_id(self) -> Optional[str]:
        return self._uid_from(self._current_user())

    def _global_roles_of(self, user: Any) -> Set[str]:
        out: Set[str] = set()
        if not user:
            return out
        uid = (getattr(user, "username", None) or getattr(user, "email", None) or getattr(user, "id", None) or "").strip().lower()
        def _has(key: str) -> bool:
            raw = str(self._sm.get(self.FEATURE_ID, key, "") or "")
            parts = [p.strip().lower() for p in raw.replace(";", ",").split(",") if p.strip()]
            return uid in parts
        if _has("rbac_admins"): out.add("ADMIN")
        if _has("rbac_qmb"): out.add("QMB")
        return out

    # --------------------------------------------------------------- repository
    def list_documents(self, text: Optional[str], status: Optional[DocumentStatus] = None, active_only: bool = False) -> List[DocumentRecord]:
        assert self._repo, "Controller not initialized"
        return self._repo.list(status=status, text=(text or None), active_only=active_only)

    def get_document(self, doc_id: str) -> DocumentRecord:
        assert self._repo, "Controller not initialized"
        return self._repo.get(doc_id)

    def get_assignees(self, doc_id: str) -> Dict[str, List[str]]:
        assert self._repo, "Controller not initialized"
        return self._repo.get_assignees(doc_id) or {}

    def set_assignees(self, doc_id: str, a: Assignments) -> None:
        assert self._repo, "Controller not initialized"
        self._repo.set_assignees(
            doc_id,
            authors=(a.authors or None),
            reviewers=(a.reviewers or None),
            approvers=(a.approvers or None),
        )

    # --------------------------------------------------------------- assignments
    def can_assign_roles(self, doc: DocumentRecord) -> bool:
        user_id = (self.current_user_id() or "").strip().lower()
        roles_global = self._global_roles_of(self._current_user())
        if {"ADMIN", "QMB"} & roles_global:
            return True
        owner = (self._doc_owner_id(doc) or "").strip().lower()
        starter = (self._get_workflow_starter(doc) or "").strip().lower()
        return user_id and user_id in {owner, starter}

    def validate_assignments(self, reviewers: List[str], approvers: List[str]) -> Tuple[bool, str]:
        r = [s.strip() for s in (reviewers or []) if s and s.strip()]
        a = [s.strip() for s in (approvers or []) if s and s.strip()]
        if not r or not a:
            return False, "Sowohl Prüfer als auch Freigeber müssen zugewiesen werden."
        distinct = {u.lower() for u in r} | {u.lower() for u in a}
        if len(distinct) < 2:
            return False, "Die Menge Prüfer ∪ Freigeber muss mindestens zwei verschiedene Personen enthalten."
        return True, ""

    def list_users_for_dialog(self) -> Optional[List[Dict[str, str]]]:
        if self._rbac and hasattr(self._rbac, "list_users"):
            try:
                users = self._rbac.list_users()  # type: ignore
                out: List[Dict[str, str]] = []
                for u in (users or []):
                    ident = u.get("id") or u.get("username") or u.get("email")
                    if not ident: continue
                    out.append({
                        "id": str(ident),
                        "username": str(u.get("username") or ident),
                        "email": str(u.get("email") or ""),
                        "full_name": str(u.get("full_name") or u.get("name") or ""),
                    })
                if out: return out
            except Exception:
                pass

        # Settings fallback
        try:
            role_keys = ["rbac_admins", "rbac_qmb", "rbac_authors", "rbac_reviewers", "rbac_approvers", "rbac_readers"]
            members: Set[str] = set()
            for key in role_keys:
                raw = str(self._sm.get(self.FEATURE_ID, key, "") or "")
                parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
                members.update(parts)
            if members:
                return [{"id": m, "username": m, "email": "", "full_name": ""} for m in sorted(members)]
        except Exception:
            pass

        cu = self._current_user()
        if cu:
            ident = getattr(cu, "username", None) or getattr(cu, "email", None) or getattr(cu, "id", None)
            if ident:
                return [{
                    "id": str(getattr(cu, "id", ident)),
                    "username": str(getattr(cu, "username", ident)),
                    "email": str(getattr(cu, "email", "")),
                    "full_name": str(getattr(cu, "full_name", "") or getattr(cu, "name", "")),
                }]
        return None

    # -------------------------------------------------------------- docx meta
    def get_docx_meta(self, doc: DocumentRecord) -> Dict[str, Any]:
        path = self._find_docx_candidate(doc)
        if not path:
            return {}
        core, _comments = extract_core_and_comments(path)
        return core or {}

    def _find_docx_candidate(self, doc: DocumentRecord) -> Optional[str]:
        cur = doc.current_file_path or ""
        if cur.lower().endswith(".docx") and os.path.isfile(cur):
            return cur
        folder = os.path.dirname(cur) if cur else None
        if folder and os.path.isdir(folder):
            cands = [p for p in glob.glob(os.path.join(folder, "*.docx")) if os.path.isfile(p)]
            pref = [p for p in cands if os.path.basename(p).startswith(f"{doc.doc_id.value}_")]
            return pref[0] if pref else (cands[0] if cands else None)
        return None

    # ----------------------------------------------------------- state helpers
    def _doc_owner_id(self, doc: DocumentRecord) -> Optional[str]:
        cand = getattr(doc, "owner_user_id", None) or getattr(doc, "created_by", None)
        if isinstance(cand, str) and cand.strip():
            return cand.strip()
        if self._repo and hasattr(self._repo, "get_owner"):
            try:
                val = self._repo.get_owner(doc.doc_id.value)  # type: ignore
                if isinstance(val, str) and val.strip():
                    return val.strip()
            except Exception:
                pass
        try:
            ass = self.get_assignees(doc.doc_id.value)
            authors = ass.get("AUTHOR") or []
            if authors:
                return str(authors[0])
        except Exception:
            pass
        return None

    def _is_workflow_active(self, doc: DocumentRecord) -> bool:
        if doc.status != DocumentStatus.DRAFT:
            return True
        return bool(self._active_cache.get(doc.doc_id.value, False))

    def _set_workflow_active(self, doc_id: str, active: bool) -> None:
        self._active_cache[doc_id] = bool(active)

    def _get_workflow_starter(self, doc: DocumentRecord) -> Optional[str]:
        return self._starter_cache.get(doc.doc_id.value)

    def _set_workflow_starter(self, doc_id: str, user_id: str) -> None:
        self._starter_cache[doc_id] = user_id

    def _get_last_reviewer(self, doc_id: str) -> Optional[str]:
        return self._last_reviewer_cache.get(doc_id)

    def _set_last_reviewer(self, doc_id: str, user_id: str) -> None:
        if user_id: self._last_reviewer_cache[doc_id] = user_id

    # ---------------------------------------------------- controls computation
    def compute_controls_state(self, doc: Optional[DocumentRecord]) -> ControlsState:
        if not doc:
            return ControlsState(False, False, False, False, False, False, False, "Workflow starten", "Weiter")

        user = self._current_user()
        uid = (self._uid_from(user) or "")
        roles_global = self._global_roles_of(user)
        assigned = self._assigned_roles(doc.doc_id.value, uid)
        active = self._is_workflow_active(doc)

        can_open = bool(doc.current_file_path)
        can_copy = doc.status in {DocumentStatus.PUBLISHED, (self._STATUS_OBSOLETE or DocumentStatus.PUBLISHED)}
        can_archive = (doc.status == DocumentStatus.PUBLISHED) and bool({"ADMIN", "QMB"} & roles_global)

        can_assign_roles = self.can_assign_roles(doc)

        if doc.status == DocumentStatus.DRAFT and not active:
            workflow_text = "Workflow starten"; can_toggle = True
            next_text = "Zur Prüfung einreichen"; can_next = False; can_back = False
        else:
            workflow_text = "Workflow abbrechen"
            starter = (self._get_workflow_starter(doc) or "").strip().lower()
            can_toggle = self._wf.can_abort_workflow(
                roles=roles_global, status=doc.status, starter_user_id=starter, current_user_id=uid, active=True
            )
            if doc.status == DocumentStatus.DRAFT:
                next_text = "Zur Prüfung einreichen"
                can_next = self._wf.can_submit_review(roles=roles_global, assigned=assigned, status=doc.status)
            elif doc.status == DocumentStatus.IN_REVIEW:
                next_text = "Freigabe einholen"
                can_next = self._wf.can_request_approval(roles=roles_global, assigned=assigned, status=doc.status)
            elif doc.status == DocumentStatus.APPROVAL:
                next_text = "Veröffentlichen"
                can_next = self._wf.can_publish(roles=roles_global, assigned=assigned, status=doc.status)
            else:
                next_text = "Weiter"; can_next = False
            can_back = self._wf.can_back_to_draft(roles=roles_global, assigned=assigned, status=doc.status)

        return ControlsState(
            can_open=can_open,
            can_copy=can_copy,
            can_assign_roles=can_assign_roles,
            can_archive=can_archive,
            can_next=can_next,
            can_back_to_draft=can_back,
            can_toggle_workflow=can_toggle,
            workflow_text=workflow_text,
            next_text=next_text,
        )

    def _assigned_roles(self, doc_id: str, user_id: str) -> Set[str]:
        if not (doc_id and user_id and self._repo):
            return set()
        try:
            ass = self._repo.get_assignees(doc_id) or {}
        except Exception:
            return set()
        uid = user_id.strip().lower()
        out: Set[str] = set()
        for role, users in (ass or {}).items():
            if any(str(u).strip().lower() == uid for u in (users or [])):
                out.add(role.upper())
        return out

    # ------------------------------------------------------------- transitions
    def start_workflow(self, doc: DocumentRecord, ensure_assignments: callable) -> bool:
        if self._is_workflow_active(doc) or doc.status != DocumentStatus.DRAFT:
            return False
        if not ensure_assignments():
            return False
        ass = self.get_assignees(doc.doc_id.value)
        uid = self.current_user_id() or ""
        if ass.get("AUTHOR") is None or len(ass.get("AUTHOR", [])) == 0:
            self.set_assignees(doc.doc_id.value, Assignments(authors=[uid],
                                                             reviewers=ass.get("REVIEWER") or [],
                                                             approvers=ass.get("APPROVER") or []))
        self._set_workflow_active(doc.doc_id.value, True)
        self._set_workflow_starter(doc.doc_id.value, uid)
        return True

    def abort_workflow(self, doc: DocumentRecord, reason_provider: callable, password_provider: callable) -> Tuple[bool, str]:
        uid = self.current_user_id() or ""
        roles = self._global_roles_of(self._current_user())
        if not self._wf.can_abort_workflow(
            roles=roles, status=doc.status, starter_user_id=self._get_workflow_starter(doc),
            current_user_id=uid, active=True
        ):
            return False, "Abbruch nicht erlaubt."
        reason = reason_provider()
        if not reason:
            return False, "Abbruch ohne Begründung abgewiesen."
        pwd = password_provider()
        if not (pwd and self._verify_password(uid, pwd)):
            return False, "Passwortprüfung fehlgeschlagen."
        if not self._repo:
            return False, "Repository nicht initialisiert."
        if doc.status != DocumentStatus.DRAFT:
            self._repo.set_status(doc.doc_id.value, DocumentStatus.DRAFT, uid, reason)
            self._restore_docx_best_effort(doc.doc_id.value)
        self._set_workflow_active(doc.doc_id.value, False)
        return True, ""

    def forward_transition(self, doc: DocumentRecord, ask_reason: callable, sign_pdf: callable) -> Tuple[bool, str]:
        assert self._repo, "Controller not initialized"
        uid = self.current_user_id() or ""
        roles = self._global_roles_of(self._current_user())
        assigned = self._assigned_roles(doc.doc_id.value, uid)

        if doc.status == DocumentStatus.DRAFT:
            if not self._is_workflow_active(doc):
                return False, "Bitte zuerst den Workflow starten."
            if not self._wf.can_submit_review(roles=roles, assigned=assigned, status=doc.status):
                return False, "Keine Berechtigung zum Einreichen."
            pdf = self._repo.generate_review_pdf(doc.doc_id.value)
            if not (pdf and os.path.isfile(pdf)):
                return False, "Erstellung des Prüf-PDF ist fehlgeschlagen."
            reason = ask_reason()
            if not reason: return False, "Abgebrochen."
            signed = sign_pdf(pdf, reason)
            if not signed: return False, "Signaturvorgang abgebrochen."
            self._repo.attach_signed_pdf(doc.doc_id.value, signed, "submit_review", uid, reason)
            self._repo.set_status(doc.doc_id.value, DocumentStatus.IN_REVIEW, uid, reason)
            # actual editor is the submitter; signature stored by repo
            return True, ""

        if doc.status == DocumentStatus.IN_REVIEW:
            if not self._wf.can_request_approval(roles=roles, assigned=assigned, status=doc.status):
                return False, "Schritt nicht erlaubt."
            pdf = doc.current_file_path or ""
            if not (pdf and pdf.lower().endswith(".pdf") and os.path.isfile(pdf)):
                pdf = self._repo.generate_review_pdf(doc.doc_id.value) or ""
            if not (pdf and os.path.isfile(pdf)):
                return False, "Kein aktives PDF verfügbar."
            reason = ask_reason()
            if not reason: return False, "Abgebrochen."
            signed = sign_pdf(pdf, reason)
            if not signed: return False, "Signaturvorgang abgebrochen."
            self._repo.attach_signed_pdf(doc.doc_id.value, signed, "request_approval", uid, reason)
            self._repo.set_status(doc.doc_id.value, DocumentStatus.APPROVAL, uid, reason)
            self._set_last_reviewer(doc.doc_id.value, uid)  # block same person at publish
            return True, ""

        if doc.status == DocumentStatus.APPROVAL:
            last_reviewer = (self._get_last_reviewer(doc.doc_id.value) or "").strip().lower()
            if last_reviewer and last_reviewer == (uid.strip().lower()):
                return False, "Die prüfende Person darf nicht freigeben."
            if not self._wf.can_publish(roles=roles, assigned=assigned, status=doc.status):
                return False, "Schritt nicht erlaubt."
            pub_pdf = self._repo.export_pdf_with_version_suffix(doc.doc_id.value)
            if not (pub_pdf and os.path.isfile(pub_pdf)):
                return False, "Versioniertes PDF konnte nicht erstellt werden."
            reason = ask_reason()
            if not reason: return False, "Abgebrochen."
            signed = sign_pdf(pub_pdf, reason)
            if not signed: return False, "Signaturvorgang abgebrochen."
            self._repo.attach_signed_pdf(doc.doc_id.value, signed, "publish", uid, reason)
            self._repo.set_status(doc.doc_id.value, DocumentStatus.PUBLISHED, uid, reason)
            self._set_workflow_active(doc.doc_id.value, False)
            return True, ""

        return False, "Kein weiterer Schritt verfügbar."

    def backward_to_draft(self, doc: DocumentRecord, ask_reason: callable) -> Tuple[bool, str]:
        uid = self.current_user_id() or ""
        roles = self._global_roles_of(self._current_user())
        assigned = self._assigned_roles(doc.doc_id.value, uid)

        if not self._wf.can_back_to_draft(roles=roles, assigned=assigned, status=doc.status):
            return False, "Rücksprung nicht erlaubt."

        reason = ask_reason()
        if not reason: return False, "Abgebrochen."
        assert self._repo, "Controller not initialized"
        self._repo.set_status(doc.doc_id.value, DocumentStatus.DRAFT, uid, reason)
        self._restore_docx_best_effort(doc.doc_id.value)
        self._set_workflow_active(doc.doc_id.value, True)
        return True, ""

    def archive(self, doc: DocumentRecord, ask_reason: callable) -> Tuple[bool, str]:
        status_target = self._STATUS_ARCHIVED or self._STATUS_OBSOLETE
        if not status_target:
            return False, "Kein Zielstatus ARCHIVED/OBSOLETE verfügbar."
        user = self._current_user()
        roles_global = self._global_roles_of(user)
        if not {"ADMIN", "QMB"} & roles_global:
            return False, "Archivieren nur für ADMIN oder QMB."
        if doc.status != DocumentStatus.PUBLISHED:
            return False, "Nur veröffentlichte Dokumente können archiviert werden."

        reason = ask_reason()
        if not reason: return False, "Abgebrochen."
        assert self._repo, "Controller not initialized"

        # 1) Update status
        uid = self.current_user_id() or ""
        self._repo.set_status(doc.doc_id.value, status_target, uid, reason)

        # 2) Move on-disk folder into <root>/archived/<doc_id> and fix DB path
        try:
            # Determine root/doc_dir from current path
            cur = doc.current_file_path or ""
            # doc_dir is parent of version dir
            doc_dir = os.path.dirname(os.path.dirname(cur)) if cur else None
            if not doc_dir or not os.path.isdir(doc_dir):
                # fallback to repo helper if available
                if hasattr(self._repo, "_doc_dir"):
                    doc_dir = self._repo._doc_dir(doc.doc_id.value)  # type: ignore
            root = getattr(self._repo, "_cfg", {}).get("root_path", None) if hasattr(self._repo, "_cfg") else None
            if not root and doc_dir:
                root = os.path.dirname(doc_dir)
            arch_root = os.path.join(root, "archived") if root else None
            if arch_root:
                os.makedirs(arch_root, exist_ok=True)
                dest_dir = os.path.join(arch_root, doc.doc_id.value)
                # Ensure unique target
                if os.path.exists(dest_dir):
                    suffix = datetime.utcnow().strftime("%Y%m%d%H%M%S")
                    dest_dir = os.path.join(arch_root, f"{doc.doc_id.value}_{suffix}")
                if doc_dir and os.path.isdir(doc_dir):
                    shutil.move(doc_dir, dest_dir)

                    # Fix DB current_file_path to reflect new location
                    rel = None
                    if cur and doc_dir and cur.startswith(doc_dir):
                        rel = cur[len(doc_dir):].lstrip(os.sep)
                    new_cur = os.path.join(dest_dir, rel) if rel else None
                    if new_cur:
                        try:
                            self._repo._conn.execute(
                                "UPDATE documents SET current_file_path=? WHERE doc_id=?",
                                (new_cur, doc.doc_id.value)
                            )
                            self._repo._conn.commit()
                        except Exception:
                            pass
        except Exception:
            # Do not fail archive if move fails; status is already updated.
            pass

        return True, ""

    # --------------------------------------------------------- actual actors & details
    def get_actual_actors(self, doc: DocumentRecord) -> Dict[str, Any]:
        """
        Returns display names of the users who actually *executed* steps,
        and the signature timestamps.
        Mapping:
          - editor       := user who signed 'submit_review'
          - reviewer     := user who signed 'request_approval'
          - publisher    := user who signed 'publish'
        """
        out = {"editor": None, "reviewer": None, "publisher": None,
               "editor_dt": None, "reviewer_dt": None, "publisher_dt": None}
        if not self._repo:
            return out
        try:
            q = "SELECT step,user_id,signed_at FROM signatures WHERE doc_id=? ORDER BY signed_at ASC"
            rows = self._repo._conn.execute(q, (doc.doc_id.value,)).fetchall()
            first_by_step: Dict[str, tuple[str, str]] = {}
            for r in rows or []:
                step = (r["step"] or "").strip().lower()
                if step not in first_by_step:
                    first_by_step[step] = (str(r["user_id"] or ""), str(r["signed_at"] or ""))
            # Resolve names
            def disp(uid: Optional[str]) -> Optional[str]:
                if not uid: return None
                return self._resolve_display_name(uid) or uid
            if "submit_review" in first_by_step:
                u, dt = first_by_step["submit_review"]; out["editor"] = disp(u); out["editor_dt"] = dt
            if "request_approval" in first_by_step:
                u, dt = first_by_step["request_approval"]; out["reviewer"] = disp(u); out["reviewer_dt"] = dt
            if "publish" in first_by_step:
                u, dt = first_by_step["publish"]; out["publisher"] = disp(u); out["publisher_dt"] = dt
        except Exception:
            pass
        return out

    def get_document_details(self, doc: DocumentRecord) -> Dict[str, Any]:
        """
        Returns a rich details dict to be shown in Overview.
        Keys (as requested):
          title, editor, reviewer, publisher, description, documenttype,
          documentpath, last_modified, editor_signature_date, reviewer_signature_date,
          publisher_signature_date, valid_by_date, workflow_status, actual_filetype,
          doc_id, docx_comment_list, pdf_comment_list
        """
        core = {}
        try:
            core = self.get_docx_meta(doc) or {}
        except Exception:
            core = {}

        exec_info = self.get_actual_actors(doc)

        # DOCX comments (latest version)
        docx_comments: List[Dict[str, Any]] = []
        pdf_comments: List[Dict[str, Any]] = []  # not implemented yet

        if self._repo and hasattr(self._repo, "get_docx_comments_for_version"):
            try:
                # let repo determine version label from meta if not passed
                docx_comments = self._repo.get_docx_comments_for_version(doc.doc_id.value, version_label=None)  # type: ignore
            except Exception:
                docx_comments = []

        # Compose
        path = doc.current_file_path or ""
        actual_ftype = os.path.splitext(path)[1][1:].upper() if path else ""

        details = {
            "title": doc.title,
            "editor": exec_info.get("editor"),
            "reviewer": exec_info.get("reviewer"),
            "publisher": exec_info.get("publisher"),
            "description": getattr(doc, "change_note", None) or core.get("subject") or core.get("keywords"),
            "documenttype": doc.doc_type,
            "documentpath": path,
            "last_modified": getattr(doc, "updated_at", None).isoformat(timespec="seconds") if getattr(doc, "updated_at", None) else None,
            "editor_signature_date": exec_info.get("editor_dt"),
            "reviewer_signature_date": exec_info.get("reviewer_dt"),
            "publisher_signature_date": exec_info.get("publisher_dt"),
            "valid_by_date": getattr(doc, "next_review", None).isoformat(timespec="seconds") if getattr(doc, "next_review", None) else None,
            "workflow_status": doc.status.name,
            "actual_filetype": actual_ftype or ("DOCX" if (path.lower().endswith(".docx")) else ("PDF" if path.lower().endswith(".pdf") else None)),
            "doc_id": doc.doc_id.value,
            "docx_comment_list": docx_comments,
            "pdf_comment_list": pdf_comments,
        }
        return details

    def _resolve_display_name(self, user_id: str) -> Optional[str]:
        """Resolve display name via RBAC if available."""
        uid = (user_id or "").strip()
        if not uid: return None
        # Direct method
        if self._rbac and hasattr(self._rbac, "get_user"):
            try:
                u = self._rbac.get_user(uid)  # type: ignore
                if u:
                    return str(u.get("full_name") or u.get("name") or u.get("username") or u.get("email") or uid)
            except Exception:
                pass
        # Search within list_users fallback
        users = self.list_users_for_dialog() or []
        for u in users:
            if str(u.get("id") or "").strip().lower() == uid.lower() \
               or str(u.get("username") or "").strip().lower() == uid.lower() \
               or str(u.get("email") or "").strip().lower() == uid.lower():
                return str(u.get("full_name") or u.get("username") or u.get("email") or uid)
        return None

    # ------------------------------------------------------------ docx restore
    def _restore_docx_best_effort(self, doc_id: str) -> None:
        assert self._repo, "Controller not initialized"
        rec = self._repo.get(doc_id)
        cur = rec.current_file_path or ""
        if cur.lower().endswith(".docx"):
            return
        folder = os.path.dirname(cur) if cur else os.path.dirname(self._repo.get(doc_id).current_file_path or "")
        candidates: List[str] = []
        if folder and os.path.isdir(folder):
            try:
                candidates = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".docx")]
                candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            except Exception:
                candidates = []
        picked = candidates[0] if candidates else None
        if picked and os.path.isfile(picked):
            try:
                self._repo.check_in(doc_id, self.current_user_id() or "", picked, "Restore DOCX after backward transition")
            except Exception:
                pass

    # --------------------------------------------------------- password checks
    def _verify_password(self, uid: str, pwd: str) -> bool:
        def _truthy(x: Any) -> bool:
            if isinstance(x, bool): return x
            if isinstance(x, dict): return x.get("ok") is True or x.get("authenticated") is True
            if hasattr(x, "ok"):
                try: return bool(getattr(x, "ok"))
                except Exception: pass
            return bool(x)
        try:
            auth = getattr(AppContext, "auth", None)
            auth = auth() if callable(auth) else auth
            if auth:
                for name in ("verify_password", "check_password", "authenticate", "login"):
                    fn = getattr(auth, name, None)
                    if callable(fn):
                        try:
                            if _truthy(fn(uid, pwd)): return True
                        except Exception: pass
        except Exception: pass
        if self._rbac:
            for name in ("verify_password", "check_password", "authenticate", "login"):
                fn = getattr(self._rbac, name, None)
                if callable(fn):
                    try:
                        if _truthy(fn(uid, pwd)): return True
                    except Exception: pass
        return False

    # ------------------------------------------------------------ public API
    def list_published_documents(self) -> List[Dict[str, Any]]:
        """
        Public method for other modules to retrieve a minimal list of *published* documents.
        Returns a list of dicts with id, title, type, version, path and timestamps.
        """
        assert self._repo, "Controller not initialized"
        recs = self._repo.list(status=DocumentStatus.PUBLISHED, text=None)
        out: List[Dict[str, Any]] = []
        for r in recs:
            out.append({
                "doc_id": r.doc_id.value,
                "title": r.title,
                "doc_type": r.doc_type,
                "version": r.version_label,
                "status": r.status.name,
                "path": r.current_file_path,
                "updated_at": (r.updated_at.isoformat(timespec="seconds") if getattr(r, "updated_at", None) else None),
                "next_review": (r.next_review.isoformat(timespec="seconds") if getattr(r, "next_review", None) else None),
            })
        return out
