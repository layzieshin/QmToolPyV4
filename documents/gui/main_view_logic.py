# documents/gui/main_view_logic.py
"""
Controller/Logic layer for the Documents main view.

Key points:
- Forward step requires signature (interactive) and does NOT advance status on cancel/failure.
- PDF generation uses repository hook (which converts DOCX to PDF without markup).
- Reasons (change notes) are collected appropriately.
- NEW: workflow_active persisted; button text & enablement use persisted state + permission guards.
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
        """
        Business rule:
          - both roles required (non-empty)
          - sets must be disjoint (no user in both roles)
          - at least 2 distinct people across both roles (implizit durch Disjointness + Non-Empty)
        """
        r = [s.strip() for s in (reviewers or []) if s and s.strip()]
        a = [s.strip() for s in (approvers or []) if s and s.strip()]
        if not r or not a:
            return False, "Sowohl Prüfer als auch Freigeber müssen zugewiesen werden."

        rset = {u.lower() for u in r}
        aset = {u.lower() for u in a}

        if rset & aset:
            return False, "Eine Person darf nicht gleichzeitig Prüfer und Freigeber sein."

        # optional streng: mindestens 2 Personen insgesamt
        if len(rset | aset) < 2:
            return False, "Die Rollen müssen insgesamt mindestens zwei unterschiedliche Personen enthalten."

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
        """
        Active by definition for non-DRAFT (REVIEW/APPROVED/EFFECTIVE).
        For DRAFT we consult the repository-persisted flag, fallback to RAM cache.
        """
        if doc.status != DocumentStatus.DRAFT:
            return True
        # Persisted flag first
        if self._repo and hasattr(self._repo, "is_workflow_active"):
            try:
                return bool(self._repo.is_workflow_active(doc.doc_id.value))  # type: ignore
            except Exception:
                pass
        return bool(self._active_cache.get(doc.doc_id.value, False))

    def _set_workflow_active(self, doc_id: str, active: bool, started_by: Optional[str] = None) -> None:
        self._active_cache[doc_id] = bool(active)
        if self._repo and hasattr(self._repo, "set_workflow_active"):
            try:
                self._repo.set_workflow_active(doc_id, active, started_by)  # type: ignore
            except Exception:
                pass

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
        can_copy = doc.status in {DocumentStatus.EFFECTIVE, (self._STATUS_OBSOLETE or DocumentStatus.EFFECTIVE)}
        can_archive = (doc.status == DocumentStatus.EFFECTIVE) and bool({"ADMIN", "QMB"} & roles_global)

        can_assign_roles = self.can_assign_roles(doc)

        if doc.status == DocumentStatus.DRAFT and not active:
            workflow_text = "Workflow starten"; can_toggle = True
            next_text = "Zur Prüfung einreichen"; can_next = False; can_back = False
        else:
            workflow_text = "Workflow abbrechen"
            starter = (self._get_workflow_starter(doc) or "").strip().lower()
            # Abbrechen nur, wenn erlaubt:
            can_toggle = self._wf.can_abort_workflow(
                roles=roles_global, status=doc.status, starter_user_id=starter, current_user_id=uid, active=True
            )
            if doc.status == DocumentStatus.DRAFT:
                next_text = "Zur Prüfung einreichen"
                can_next = self._wf.can_submit_review(roles=roles_global, assigned=assigned, status=doc.status)
            elif doc.status == DocumentStatus.REVIEW:
                next_text = "Genehmigen"
                can_next = self._wf.can_approve(roles=roles_global, assigned=assigned, status=doc.status)
            elif doc.status == DocumentStatus.APPROVED:
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

        # Author not set? – ensure the current user is author at minimum
        if not ass.get("AUTHOR"):
            self.set_assignees(
                doc.doc_id.value,
                Assignments(
                    authors=[uid],
                    reviewers=ass.get("REVIEWER") or [],
                    approvers=ass.get("APPROVER") or []
                )
            )
            ass = self.get_assignees(doc.doc_id.value)

        # <-- NEU: harte Geschäftslogikprüfung
        ok, msg = self.validate_assignments(ass.get("REVIEWER") or [], ass.get("APPROVER") or [])
        if not ok:
            # UI zeigt evtl. keine Nachricht – False reicht, um Start zu verhindern.
            return False

        self._set_workflow_active(doc.doc_id.value, True, started_by=uid)
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
        # Persistent flag zurücksetzen
        self._set_workflow_active(doc.doc_id.value, False)
        return True, ""

    def forward_transition(self, doc: DocumentRecord, ask_reason, sign_pdf):
        """
        Führt den nächsten Workflow-Schritt aus.
        WICHTIG:
          - Wenn der Schritt eine Signatur erfordert und diese abgebrochen/fehlgeschlagen ist,
            wird KEIN Statuswechsel vorgenommen.
          - Die Signatur-UI erwartet (pdf_path, reason), daher holen wir den Grund VORHER.
        """
        assert self._repo, "Repository nicht initialisiert"

        user = self._current_user()
        uid = self._uid_from(user) or ""
        roles_global = self._global_roles_of(user)
        assigned = self._assigned_roles(doc.doc_id.value, uid)

        action_id = self._wf.next_action(roles=roles_global, assigned=assigned, status=doc.status)
        if not action_id:
            return False, "Kein nächster Schritt verfügbar."

        requires_signature = self._wf.requires_signature_for(action_id)
        reason_for_signature: Optional[str] = None

        if requires_signature:
            # Grund erfragen:
            try:
                if callable(ask_reason):
                    reason_for_signature = ask_reason()
                    if reason_for_signature is None:
                        return False, "Abgebrochen."
            except Exception:
                reason_for_signature = ""

            pdf = self._repo.generate_review_pdf(doc.doc_id.value)
            if not pdf:
                return False, "PDF konnte für die Signatur nicht erstellt werden."

            if not callable(sign_pdf):
                return False, "Signatur erforderlich, aber keine Signaturfunktion verfügbar."
            signed_pdf_path = sign_pdf(pdf, reason_for_signature or "")
            if not signed_pdf_path:
                return False, "Signatur abgebrochen."

            ok, msg = self._repo.attach_signed_pdf(
                doc_id=doc.doc_id.value,
                signed_pdf_path=signed_pdf_path,
                step=action_id,
                user_id=uid,
                reason=reason_for_signature or None,
            )
            if not ok:
                return False, msg or "Signiertes PDF konnte nicht übernommen werden."

        if action_id == "publish":
            versioned = self._repo.export_pdf_with_version_suffix(doc.doc_id.value)
            if not versioned:
                return False, "Versionierte PDF konnte nicht abgelegt werden."

        next_status = self._wf.next_status_for(action_id, doc.status)
        if not next_status:
            return False, "Zielstatus nicht bestimmbar."

        status_reason = None
        try:
            if self._wf.requires_reason_for(next_status) and callable(ask_reason):
                status_reason = ask_reason()
        except Exception:
            status_reason = None

        self._repo.set_status(doc.doc_id.value, next_status, uid, status_reason)
        return True, None

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
        # Achtung: Back-to-draft behält den Workflow als aktiv (nicht abbrechen)
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
        if doc.status != DocumentStatus.EFFECTIVE:
            return False, "Nur wirksame Dokumente können archiviert werden."

        reason = ask_reason()
        if not reason: return False, "Abgebrochen."
        assert self._repo, "Controller not initialized"

        uid = self.current_user_id() or ""
        self._repo.set_status(doc.doc_id.value, status_target, uid, reason)
        # Persistenter Flag ist ab Veröffentlichung egal; auf Nummer sicher setzen wir ihn aus:
        self._set_workflow_active(doc.doc_id.value, False)

        # Ordner verschieben (best effort)...
        try:
            cur = doc.current_file_path or ""
            doc_dir = os.path.dirname(os.path.dirname(cur)) if cur else None
            if not doc_dir or not os.path.isdir(doc_dir):
                if hasattr(self._repo, "_doc_dir"):
                    doc_dir = self._repo._doc_dir(doc.doc_id.value)  # type: ignore
            root = getattr(self._repo, "_cfg", {}).root_path if hasattr(self._repo, "_cfg") else None
            if not root and doc_dir:
                root = os.path.dirname(doc_dir)
            arch_root = os.path.join(root, "archived") if root else None
            if arch_root and doc_dir and os.path.isdir(doc_dir):
                os.makedirs(arch_root, exist_ok=True)
                dest_dir = os.path.join(arch_root, doc.doc_id.value)
                if os.path.exists(dest_dir):
                    suffix = datetime.utcnow().strftime("%Y%m%d%H%M%S")
                    dest_dir = os.path.join(arch_root, f"{doc.doc_id.value}_{suffix}")
                shutil.move(doc_dir, dest_dir)

                rel = None
                if cur and cur.startswith(doc_dir):
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
            pass

        return True, ""

    # --------------------------------------------------------- actual actors & details
    def get_actual_actors(self, doc: DocumentRecord) -> Dict[str, Any]:
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
            def disp(uid: Optional[str]) -> Optional[str]:
                if not uid: return None
                return self._resolve_display_name(uid) or uid
            if "submit_review" in first_by_step:
                u, dt = first_by_step["submit_review"]; out["editor"] = disp(u); out["editor_dt"] = dt
            # Support both old and new action names for backward compatibility
            if "approve" in first_by_step:
                u, dt = first_by_step["approve"]; out["reviewer"] = disp(u); out["reviewer_dt"] = dt
            elif "request_approval" in first_by_step:
                u, dt = first_by_step["request_approval"]; out["reviewer"] = disp(u); out["reviewer_dt"] = dt
            if "publish" in first_by_step:
                u, dt = first_by_step["publish"]; out["publisher"] = disp(u); out["publisher_dt"] = dt
        except Exception:
            pass
        return out

    def get_document_details(self, doc: DocumentRecord) -> Dict[str, Any]:
        core = {}
        try:
            core = self.get_docx_meta(doc) or {}
        except Exception:
            core = {}

        exec_info = self.get_actual_actors(doc)

        docx_comments: List[Dict[str, Any]] = []
        pdf_comments: List[Dict[str, Any]] = []

        if self._repo and hasattr(self._repo, "get_docx_comments_for_version"):
            try:
                docx_comments = self._repo.get_docx_comments_for_version(doc.doc_id.value, version_label=None)  # type: ignore
            except Exception:
                docx_comments = []

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
        uid = (user_id or "").strip()
        if not uid: return None
        if self._rbac and hasattr(self._rbac, "get_user"):
            try:
                u = self._rbac.get_user(uid)  # type: ignore
                if u:
                    return str(u.get("full_name") or u.get("name") or u.get("username") or u.get("email") or uid)
            except Exception:
                pass
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
        assert self._repo, "Controller not initialized"
        recs = self._repo.list(status=DocumentStatus.EFFECTIVE, text=None)
        out: List[Dict[str, Any]] = []
        for r in recs:
            version = getattr(r, "version_label", None) or f"{getattr(r, 'version_major', 1)}.{getattr(r, 'version_minor', 0)}"
            out.append({
                "doc_id": r.doc_id.value,
                "title": r.title,
                "doc_type": r.doc_type,
                "version": version,
                "status": r.status.name,
                "path": r.current_file_path,
                "updated_at": (r.updated_at.isoformat(timespec="seconds") if getattr(r, "updated_at", None) else None),
                "next_review": (r.next_review.isoformat(timespec="seconds") if getattr(r, "next_review", None) else None),
            })
        return out
