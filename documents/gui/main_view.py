"""
Main View for the Document Control module – Final Version

This GUI implements a modern, user-friendly interface for a document
control workflow. It provides a vertically split layout with a document
list and detailed tabs (overview, metadata, comments, read receipts). Users
can start or continue workflows, sign and pass documents to reviewers and
approvers, revert to draft, and produce watermarked copies of published
documents.

Signatures are captured interactively via AppContext.signature().place_and_sign,
ensuring a secure and user-driven process. Role assignment is integrated
into the workflow start, and the interface adapts based on the document's
status to show appropriate actions.

This file is self-contained for final delivery and may need integration
with existing project modules (e.g. translation keys, signature API).
"""

from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Set, Any

try:
    from core.common.app_context import AppContext, T  # type: ignore
except Exception:
    # Fallback definitions if AppContext/T are unavailable during static analysis
    class AppContext:
        app_storage_dir: str | None = None
        current_user: object | None = None
        @staticmethod
        def signature():
            raise RuntimeError("Signature API not available")
        translate = staticmethod(lambda key, default=None: default)
    def T(key: str) -> str:  # type: ignore
        return ""

from core.settings.logic.settings_manager import SettingsManager  # type: ignore
from documents.models.document_models import DocumentRecord, DocumentStatus
from documents.logic.repository import DocumentsRepository, RepoConfig
from documents.logic.workflow_engine import WorkflowEngine
from documents.logic.permissions import ModulePermissions
from documents.logic.rbac_service import RBACService

from documents.gui.dialogs.metadata_dialog import MetadataDialog
from documents.gui.dialogs.change_note_dialog import ChangeNoteDialog
from documents.gui.dialogs.assign_roles_dialog import AssignRolesDialog


class DocumentsView(ttk.Frame):
    """Main GUI view for the document control module."""

    _FEATURE_ID = "documents"

    def __init__(self, parent: tk.Misc, *, settings_manager: SettingsManager) -> None:
        super().__init__(parent)
        self._sm = settings_manager
        self._wf = WorkflowEngine()
        self._perms = ModulePermissions(self._sm)
        self._repo = DocumentsRepository(self._load_repo_cfg())
        self._rbac = RBACService(self._repo._cfg["db_path"], self._sm)
        self._enable_checkout = bool(int(self._sm.get(self._FEATURE_ID, "enable_checkout", 0)))
        # Build UI
        self._build_ui()
        # Load data
        self._reload()
        self._on_select()

    # UI Construction ------------------------------------------------------
    def _build_ui(self) -> None:
        # Header with search
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        header.columnconfigure(3, weight=1)
        ttk.Label(header, text=(T("documents.title") or "Document Control"), font=("Segoe UI", 16, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text=(T("documents.filter.search") or "Search")).grid(row=0, column=1, padx=(12, 4))
        self.e_search = ttk.Entry(header, width=24)
        self.e_search.grid(row=0, column=2, sticky="w")
        ttk.Button(header, text=(T("common.search") or "Search"), command=self._reload).grid(row=0, column=3, sticky="w", padx=(6, 0))
        # Split: list and tabs
        body = ttk.Panedwindow(self, orient="horizontal")
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=6)
        # Left: document list with actions
        left = ttk.Frame(body)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)
        ttk.Label(left, text=(T("documents.list") or "Documents")).grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.tree = ttk.Treeview(left, columns=("id", "title", "type", "status", "ver"), show="headings", selectmode="browse", height=18)
        for c, w in [("id", 180), ("title", 260), ("type", 80), ("status", 120), ("ver", 70)]:
            self.tree.heading(c, text=c.upper())
            self.tree.column(c, width=w, stretch=(c == "title"))
        self.tree.grid(row=1, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._on_select())
        list_btns = ttk.Frame(left)
        list_btns.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        list_btns.columnconfigure(99, weight=1)
        ttk.Button(list_btns, text=(T("documents.btn.import") or "Import"), command=self._import).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(list_btns, text=(T("documents.btn.new_from_tpl") or "New from Template"), command=self._new_from_template).grid(row=0, column=1, padx=(0, 6))
        self.btn_out = ttk.Button(list_btns, text=(T("documents.btn.checkout") or "Check-out"), command=self._checkout)
        self.btn_in  = ttk.Button(list_btns, text=(T("documents.btn.checkin") or "Check-in"), command=self._checkin)
        if self._enable_checkout:
            self.btn_out.grid(row=0, column=2, padx=(0, 6))
            self.btn_in.grid(row=0, column=3, padx=(0, 6))
        # Right: tabs
        right = ttk.Frame(body)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        self.tabs = ttk.Notebook(right)
        self.tabs.grid(row=0, column=0, sticky="nsew")
        # Overview tab
        self.tab_over = ttk.Frame(self.tabs)
        self.tabs.add(self.tab_over, text=(T("documents.tab.overview") or "Overview"))
        self._build_overview(self.tab_over)
        # Metadata tab
        self.tab_meta = ttk.Frame(self.tabs)
        self.tabs.add(self.tab_meta, text=(T("documents.tab.meta") or "Metadata"))
        self._build_meta(self.tab_meta)
        # Comments tab
        self.tab_comments = ttk.Frame(self.tabs)
        self.tabs.add(self.tab_comments, text=(T("documents.tab.comments") or "Comments"))
        self._build_comments(self.tab_comments)
        # Reads tab
        self.tab_reads = ttk.Frame(self.tabs)
        self.tabs.add(self.tab_reads, text=(T("documents.tab.reads") or "Read Receipts"))
        self._build_reads(self.tab_reads)
        body.add(left, weight=1)
        body.add(right, weight=2)

    def _build_overview(self, host: ttk.Frame) -> None:
        host.columnconfigure(1, weight=1)
        r = 0
        ttk.Label(host, text=(T("documents.ov.id") or "ID:")).grid(row=r, column=0, sticky="w"); self.l_id = ttk.Label(host); self.l_id.grid(row=r, column=1, sticky="w"); r += 1
        ttk.Label(host, text=(T("documents.ov.title") or "Title:")).grid(row=r, column=0, sticky="w"); self.l_title = ttk.Label(host); self.l_title.grid(row=r, column=1, sticky="w"); r += 1
        ttk.Label(host, text=(T("documents.ov.type") or "Type:")).grid(row=r, column=0, sticky="w"); self.l_type = ttk.Label(host); self.l_type.grid(row=r, column=1, sticky="w"); r += 1
        ttk.Label(host, text=(T("documents.ov.status") or "Status:")).grid(row=r, column=0, sticky="w"); self.l_status = ttk.Label(host); self.l_status.grid(row=r, column=1, sticky="w"); r += 1
        ttk.Label(host, text=(T("documents.ov.version") or "Version:")).grid(row=r, column=0, sticky="w"); self.l_ver = ttk.Label(host); self.l_ver.grid(row=r, column=1, sticky="w"); r += 1
        ttk.Label(host, text=(T("documents.ov.file") or "File:")).grid(row=r, column=0, sticky="w"); self.l_file = ttk.Label(host); self.l_file.grid(row=r, column=1, sticky="w"); r += 1
        btns = ttk.Frame(host)
        btns.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        btns.columnconfigure(5, weight=1)
        self.btn_workflow = ttk.Button(btns, text=(T("documents.btn.workflow.start") or "Start Workflow"), command=self._cta_workflow)
        self.btn_next     = ttk.Button(btns, text=(T("documents.btn.next") or "Next Step"), command=self._next_step)
        self.btn_back_to_draft = ttk.Button(btns, text=(T("documents.btn.back_to_draft") or "Back to Draft"), command=self._back_to_draft)
        self.btn_open = ttk.Button(btns, text=(T("documents.btn.open") or "Open"), command=self._open_current)
        self.btn_copy = ttk.Button(btns, text=(T("documents.btn.copy") or "Copy"), command=self._copy)
        self.btn_workflow.grid(row=0, column=0, padx=(0, 6))
        self.btn_next.grid(row=0, column=1, padx=(0, 6))
        self.btn_back_to_draft.grid(row=0, column=2, padx=(0, 6))
        self.btn_open.grid(row=0, column=3, padx=(0, 6))
        self.btn_copy.grid(row=0, column=4, padx=(0, 6))

    def _build_meta(self, host: ttk.Frame) -> None:
        host.columnconfigure(1, weight=1)
        self.txt_meta = tk.Text(host, height=14, wrap="word")
        self.txt_meta.grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(0, 6))
        host.rowconfigure(0, weight=1)
        ttk.Button(host, text=(T("documents.btn.edit") or "Edit"), command=self._edit).grid(row=1, column=0, sticky="w")

    def _build_comments(self, host: ttk.Frame) -> None:
        host.columnconfigure(0, weight=1); host.rowconfigure(0, weight=1)
        cols = ("version", "author", "date", "text")
        self.tv_comments = ttk.Treeview(host, columns=cols, show="headings", height=12, selectmode="browse")
        for c, w in [("version", 100), ("author", 160), ("date", 160), ("text", 600)]:
            self.tv_comments.heading(c, text=c.upper())
            self.tv_comments.column(c, width=w, stretch=(c == "text"))
        self.tv_comments.grid(row=0, column=0, sticky="nsew")
        ttk.Label(host, text=(T("documents.comments.hint") or "Comments are extracted from the Word document (review comments)."))
        ttk.Label(host, text=(T("documents.comments.hint") or "Comments are extracted from the Word document."))
        ttk.Label(host, text=(T("documents.comments.hint") or "Comments are extracted from the Word document."))
        ttk.Label(host, text=(T("documents.comments.hint") or "Comments are extracted from the Word document."))
        ttk.Label(host, text=(T("documents.comments.hint") or "Comments are extracted from the Word document."))
        ttk.Label(host, text=(T("documents.comments.hint") or "Comments are extracted from the Word document."))

    def _build_reads(self, host: ttk.Frame) -> None:
        host.columnconfigure(0, weight=1); host.rowconfigure(0, weight=1)
        cols = ("version", "user", "read_at")
        self.tv_reads = ttk.Treeview(host, columns=cols, show="headings", height=12, selectmode="browse")
        for c, w in [("version", 100), ("user", 260), ("read_at", 180)]:
            self.tv_reads.heading(c, text=c.upper())
            self.tv_reads.column(c, width=w)
        self.tv_reads.grid(row=0, column=0, sticky="nsew")
        ttk.Button(host, text=(T("documents.btn.read") or "Mark as Read"), command=self._mark_read).grid(row=1, column=0, sticky="e", pady=(6, 0))

    # Repo configuration
    def _load_repo_cfg(self) -> RepoConfig:
        dflt_root = os.path.join(getattr(AppContext, "app_storage_dir", os.path.join(os.getcwd(), "data")), "documents_repo")
        get = lambda k, v: self._sm.get(self._FEATURE_ID, k, v)
        root = str(get("root_path", dflt_root))
        db_path = os.path.join(root, "_meta", "documents.sqlite3")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        return RepoConfig(
            root_path=root,
            db_path=db_path,
            id_prefix=str(get("id_prefix", "DOC")),
            id_pattern=str(get("id_pattern", "{YYYY}-{seq:04d}")),
            review_months=int(get("review_months", 24)),
            watermark_copy=str(get("watermark_copy", "KONTROLLIERTE KOPIE")),
        )

    # Utility functions
    def _current_user(self):
        return getattr(AppContext, "current_user", None)

    def _current_uid(self) -> Optional[str]:
        u = self._current_user()
        return getattr(u, "id", None) if u else None

    def _display_name_for_user_id(self, user_id: Optional[str]) -> str:
        if not user_id:
            return ""
        um = getattr(AppContext, "user_manager", None)
        if not um:
            return str(user_id)
        candidates = ["get_user_by_id", "get_user", "get", "find_by_id", "find_user", "load"]
        user_obj: Any = None
        for m in candidates:
            if hasattr(um, m):
                try:
                    user_obj = getattr(um, m)(user_id)
                    if user_obj:
                        break
                except Exception:
                    continue
        def _g(o: Any, *names: str) -> Optional[str]:
            for n in names:
                try:
                    if isinstance(o, dict) and n in o and o[n]:
                        return str(o[n])
                    v = getattr(o, n, None)
                    if v:
                        return str(v)
                except Exception:
                    pass
            return None
        return (_g(user_obj, "full_name", "name", "display_name") or _g(user_obj, "username") or _g(user_obj, "email") or str(user_id))

    # Table fill operations
    def _fill_overview(self, rec: Optional[DocumentRecord]) -> None:
        if not rec:
            for label in [self.l_id, self.l_title, self.l_type, self.l_status, self.l_ver, self.l_file]:
                label.configure(text="")
            for btn in [self.btn_workflow, self.btn_next, self.btn_back_to_draft, self.btn_open, self.btn_copy]:
                btn.configure(state="disabled")
            return
        self.l_id.configure(text=rec.doc_id.value)
        self.l_title.configure(text=rec.title)
        self.l_type.configure(text=rec.doc_type)
        self.l_status.configure(text=rec.status.name)
        self.l_ver.configure(text=rec.version_label)
        self.l_file.configure(text=(rec.current_file_path or "-"))

    def _fill_meta(self, rec: Optional[DocumentRecord]) -> None:
        self.txt_meta.delete("1.0", "end")
        if not rec:
            return
        owner_name = self._display_name_for_user_id(rec.created_by)
        lines = [
            f"ID: {rec.doc_id.value}",
            f"Title: {rec.title}",
            f"Type: {rec.doc_type}",
            f"Status: {rec.status.name}",
            f"Version: {rec.version_label}",
            f"Owner: {owner_name}",
            f"Valid from: {rec.valid_from or ''}",
            f"Next review: {rec.next_review or ''}",
            f"Tags: {', '.join(rec.tags) if rec.tags else ''}",
            f"Norm refs: {', '.join(rec.norm_refs) if rec.norm_refs else ''}",
            f"Locked by: {rec.locked_by or ''}",
        ]
        self.txt_meta.insert("1.0", "\n".join(lines))

    def _fill_comments(self, rec: Optional[DocumentRecord]) -> None:
        self.tv_comments.delete(*self.tv_comments.get_children())
        if not rec:
            return
        for c in self._repo.list_comments(rec.doc_id.value):
            self.tv_comments.insert("", "end", values=(c.get("version_label", ""), c.get("author", ""), c.get("date", ""), c.get("text", "")))

    def _fill_reads(self, rec: Optional[DocumentRecord]) -> None:
        self.tv_reads.delete(*self.tv_reads.get_children())
        if not rec:
            return
        for r in self._repo.list_reads(rec.doc_id.value):
            self.tv_reads.insert("", "end", values=(r["version_label"], r["user_id"], r["read_at"]))

    # Refresh controls based on state
    def _refresh_controls(self, rec: Optional[DocumentRecord]) -> None:
        # Default disable all action buttons
        for btn in [self.btn_workflow, self.btn_next, self.btn_back_to_draft, self.btn_open, self.btn_copy]:
            btn.configure(state="disabled")
        if not rec:
            return
        # Enable open/copy for published/obsolete documents
        if rec.current_file_path:
            self.btn_open.configure(state="normal")
        if rec.status in {DocumentStatus.PUBLISHED, DocumentStatus.OBSOLETE}:
            self.btn_copy.configure(state="normal")
        # Workflow buttons vary by status
        if rec.status == DocumentStatus.DRAFT:
            self.btn_workflow.configure(text=(T("documents.btn.workflow.start") or "Start Workflow"), state="normal")
            self.btn_next.configure(text=(T("documents.btn.to_review") or "Submit for Review"), state="normal")
            self.btn_back_to_draft.configure(state="disabled")
        elif rec.status == DocumentStatus.IN_REVIEW:
            self.btn_workflow.configure(text=(T("documents.btn.workflow.cont") or "Continue Workflow"), state="normal")
            self.btn_next.configure(text=(T("documents.btn.request_approval") or "Request Approval"), state="normal")
            self.btn_back_to_draft.configure(state="normal")
        elif rec.status == DocumentStatus.APPROVAL:
            self.btn_workflow.configure(text=(T("documents.btn.workflow.cont") or "Continue Workflow"), state="normal")
            self.btn_next.configure(text=(T("documents.btn.publish") or "Publish"), state="normal")
            self.btn_back_to_draft.configure(state="normal")
        else:
            # PUBLISHED/OBSOLETE: no next step; can revert to draft
            self.btn_workflow.configure(text=(T("documents.btn.workflow.none") or "No Active Workflow"), state="disabled")
            self.btn_next.configure(state="disabled")
            self.btn_back_to_draft.configure(state="normal" if rec.status != DocumentStatus.DRAFT else "disabled")
        # Check-in/out
        if self._enable_checkout:
            self.btn_out.configure(state=("normal" if rec.locked_by is None else "disabled"))
            self.btn_in.configure(state=("normal" if rec.locked_by is not None else "disabled"))

    # Public actions -------------------------------------------------------
    def _reload(self) -> None:
        text = self.e_search.get().strip() or None
        recs = self._repo.list(status=None, text=text)
        self.tree.delete(*self.tree.get_children())
        for r in recs:
            self.tree.insert("", "end", iid=r.doc_id.value, values=(r.doc_id.value, r.title, r.doc_type, r.status.name, r.version_label))

    def _on_select(self) -> None:
        rec = self._selected_record()
        self._fill_overview(rec)
        self._fill_meta(rec)
        self._fill_comments(rec)
        self._fill_reads(rec)
        self._refresh_controls(rec)

    def _import(self) -> None:
        path = filedialog.askopenfilename(parent=self, title=(T("documents.import.file") or "Choose document"), filetypes=[("Documents", "*.pdf *.docx *.xlsx *.pptx *.txt"), ("All", "*.*")])
        if not path:
            return
        rec = self._repo.create_from_file(title=None, doc_type="SOP", user_id=self._current_uid(), src_file=path)
        messagebox.showinfo(title=(T("documents.import.ok") or "Imported"), message=(T("documents.import.msg") or "Document created: ") + rec.doc_id.value, parent=self)
        self._reload()

    def _new_from_template(self) -> None:
        proj_root = os.path.abspath(os.path.join(os.getcwd()))
        tdir = os.path.join(proj_root, "templates")
        if not os.path.isdir(tdir):
            messagebox.showwarning(title=(T("documents.tpl.missing.title") or "No templates"), message=(T("documents.tpl.missing.msg") or "Folder not found: ") + tdir, parent=self)
            return
        path = filedialog.askopenfilename(parent=self, title=(T("documents.tpl.choose") or "Choose template (*.docx)"), initialdir=tdir, filetypes=[("Word template", "*.docx")])
        if not path:
            return
        base = os.path.splitext(os.path.basename(path))[0]
        dlg = ChangeNoteDialog(self, (T("documents.new.id_title") or "New document – ID and Title (Format: A02VA001_Title)"))
        self.wait_window(dlg)
        name = (dlg.result or "").strip()
        if name and "_" in name:
            target_id, title = name.split("_", 1)
        else:
            target_id, title = None, base
        rec = self._repo.create_from_template(template_path=path, target_id=target_id, title=title, doc_type="SOP", user_id=self._current_uid())
        messagebox.showinfo(title=(T("documents.created") or "Created"), message=f"Document created: {rec.doc_id.value}", parent=self)
        self._reload()

    def _checkout(self) -> None:
        if not self._enable_checkout:
            return
        rec = self._selected_record()
        if not rec:
            return
        ok = self._repo.check_out(rec.doc_id.value, self._current_uid() or "")
        if not ok:
            messagebox.showwarning(title=(T("documents.locked") or "Locked"), message=(T("documents.locked.msg") or "Document is already checked-out."), parent=self)
        self._reload()

    def _checkin(self) -> None:
        if not self._enable_checkout:
            return
        rec = self._selected_record()
        if not rec:
            return
        path = filedialog.askopenfilename(parent=self, title=(T("documents.checkin.file") or "Choose updated file (optional)"), filetypes=[("Documents", "*.pdf *.docx *.xlsx *.pptx *.txt"), ("All", "*.*")])
        reason = self._ask_reason(T("documents.checkin.note") or "Change note") or ""
        self._repo.check_in(rec.doc_id.value, self._current_uid() or "", path or None, reason)
        self._reload()

    # Workflow management --------------------------------------------------
    def _ensure_assignments(self, doc_id: str) -> bool:
        ass = self._repo.get_assignees(doc_id)
        need = (not ass.get("REVIEWER")) or (not ass.get("APPROVER"))
        if not need:
            return True
        users = self._rbac.list_users()
        dlg = AssignRolesDialog(self, users=users, current=ass)
        self.wait_window(dlg)
        if getattr(dlg, "result", None):
            self._repo.set_assignees(doc_id, authors=dlg.result.get("AUTHOR"), reviewers=dlg.result.get("REVIEWER") or [], approvers=dlg.result.get("APPROVER") or [])
            return True
        return False

    def _ask_reason(self, title: str) -> Optional[str]:
        dlg = ChangeNoteDialog(self, title)
        self.wait_window(dlg)
        reason = (dlg.result or "").strip()
        return reason or None

    def _interactive_sign(self, pdf_path: str, reason: Optional[str]) -> Optional[str]:
        if not pdf_path or not os.path.isfile(pdf_path):
            messagebox.showinfo(T("core_signature.sign.choose_pdf_first") or "Please select a PDF first.", parent=self)
            return None
        try:
            api = AppContext.signature()
        except Exception as ex:
            messagebox.showerror(T("core_signature.api_missing") or "Signature API missing.", str(ex), parent=self)
            return None
        try:
            out = api.place_and_sign(parent=self, pdf_path=pdf_path, reason=reason)
        except TypeError:
            out = api.place_and_sign(self, pdf_path, reason)
        # Normalize result
        if isinstance(out, str) and os.path.isfile(out):
            return out
        if isinstance(out, dict):
            path = out.get("out") or out.get("path") or out.get("pdf")
            if isinstance(path, str) and os.path.isfile(path):
                return path
        if hasattr(out, "path"):
            p = getattr(out, "path")
            if isinstance(p, str) and os.path.isfile(p):
                return p
        if out and os.path.isfile(pdf_path):
            return pdf_path
        return None

    def _attach_signed_output(self, doc_id: str, signed_pdf: str, step: str, user_id: str, reason: str) -> None:
        if hasattr(self._repo, "attach_signed_pdf"):
            try:
                getattr(self._repo, "attach_signed_pdf")(doc_id, signed_pdf, step, user_id, reason)
                return
            except Exception:
                pass
        try:
            self._repo.check_in(doc_id, user_id, signed_pdf, f"Signature {step}: {reason}")
        except Exception:
            pass

    def _cta_workflow(self) -> None:
        rec = self._selected_record()
        if not rec:
            return
        if rec.status == DocumentStatus.DRAFT:
            if not self._ensure_assignments(rec.doc_id.value):
                return
            messagebox.showinfo(T("documents.workflow") or "Workflow", T("documents.workflow.start_ready") or "Roles assigned. Use 'Submit for Review'.", parent=self)
        else:
            messagebox.showinfo(T("documents.workflow") or "Workflow", T("documents.workflow.cont_howto") or "Use 'Next Step' to continue.", parent=self)

    def _next_step(self) -> None:
        rec = self._selected_record()
        if not rec:
            return
        uid = self._current_uid() or ""
        # Determine action based on status
        if rec.status == DocumentStatus.DRAFT:
            if not self._ensure_assignments(rec.doc_id.value):
                return
            pdf = self._repo.generate_review_pdf(rec.doc_id.value)
            if not pdf or not os.path.isfile(pdf):
                messagebox.showerror(T("documents.reviewpdf.fail") or "Could not generate review PDF.", parent=self)
                return
            reason = self._ask_reason(T("documents.reason.to_review") or "Reason – Submit for Review")
            if not reason:
                return
            signed = self._interactive_sign(pdf, reason)
            if signed:
                self._attach_signed_output(rec.doc_id.value, signed, "submit_review", uid, reason)
                self._repo.set_status(rec.doc_id.value, DocumentStatus.IN_REVIEW, uid, reason)
        elif rec.status == DocumentStatus.IN_REVIEW:
            pdf = rec.current_file_path or ""
            if not (pdf and pdf.lower().endswith(".pdf") and os.path.isfile(pdf)):
                pdf = self._repo.generate_review_pdf(rec.doc_id.value) or ""
            if not (pdf and os.path.isfile(pdf)):
                messagebox.showerror(T("documents.sign.nopdf") or "No active PDF.", parent=self)
                return
            reason = self._ask_reason(T("documents.reason.request_approval") or "Reason – Request Approval")
            if not reason:
                return
            signed = self._interactive_sign(pdf, reason)
            if signed:
                self._attach_signed_output(rec.doc_id.value, signed, "request_approval", uid, reason)
                self._repo.set_status(rec.doc_id.value, DocumentStatus.APPROVAL, uid, reason)
        elif rec.status == DocumentStatus.APPROVAL:
            pub_pdf = self._repo.export_pdf_with_version_suffix(rec.doc_id.value)
            if not pub_pdf or not os.path.isfile(pub_pdf):
                messagebox.showerror(T("documents.publishpdf.fail") or "Could not create versioned PDF.", parent=self)
                return
            reason = self._ask_reason(T("documents.reason.publish") or "Reason – Publish")
            if not reason:
                return
            signed = self._interactive_sign(pub_pdf, reason)
            if signed:
                self._attach_signed_output(rec.doc_id.value, signed, "publish", uid, reason)
                self._repo.set_status(rec.doc_id.value, DocumentStatus.PUBLISHED, uid, reason)
        self._reload(); self._on_select()

    def _back_to_draft(self) -> None:
        rec = self._selected_record()
        if not rec:
            return
        uid = self._current_uid() or ""
        if not messagebox.askyesno(title=(T("documents.back_to_draft.title") or "Back to Draft"), message=(T("documents.back_to_draft.q") or "Reset to draft?"), parent=self):
            return
        pdf = rec.current_file_path or ""
        if not (pdf and pdf.lower().endswith(".pdf") and os.path.isfile(pdf)):
            pdf = self._repo.generate_review_pdf(rec.doc_id.value) or ""
        if not (pdf and os.path.isfile(pdf)):
            messagebox.showerror(T("documents.sign.nopdf") or "No active PDF.", parent=self)
            return
        reason = self._ask_reason(T("documents.reason.back_to_draft") or "Reason – Back to Draft")
        if not reason:
            return
        signed = self._interactive_sign(pdf, reason)
        if signed:
            self._attach_signed_output(rec.doc_id.value, signed, "back_to_draft", uid, reason)
            self._repo.set_status(rec.doc_id.value, DocumentStatus.DRAFT, uid, reason)
        self._reload(); self._on_select()

    # Copy and open
    def _copy(self) -> None:
        rec = self._selected_record()
        if not rec or rec.status != DocumentStatus.PUBLISHED:
            return
        dest_dir = filedialog.askdirectory(parent=self, title=(T("documents.copy.choose_dest") or "Choose destination"))
        if not dest_dir:
            return
        out = self._repo.copy_to_destination(rec.doc_id.value, dest_dir)
        if out:
            messagebox.showinfo(title=(T("documents.copy.ok") or "Copy created"), message=(T("documents.copy.done") or "Copy created at: ") + out, parent=self)

    def _open_current(self) -> None:
        rec = self._selected_record()
        if not rec or not rec.current_file_path:
            return
        path = rec.current_file_path
        try:
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", path])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", path])
        except Exception as ex:
            messagebox.showerror(title=(T("documents.open.error") or "Open failed"), message=str(ex), parent=self)

    def _edit(self) -> None:
        rec = self._selected_record()
        if not rec:
            return
        types = [t.strip() for t in str(self._sm.get(self._FEATURE_ID, "allowed_types", "SOP,WI,FB,CL")).split(",")]
        dlg = MetadataDialog(self, rec, allowed_types=types)
        if getattr(dlg, "result", None):
            self._repo.update_metadata(dlg.result, self._current_uid())
            self._reload(); self._on_select()

    def _mark_read(self) -> None:
        rec = self._selected_record()
        if not rec:
            return
        uid = self._current_uid()
        if not uid:
            messagebox.showwarning(title=(T("documents.read.no_user") or "Not logged in"), message=(T("documents.read.no_user.msg") or "No current user."), parent=self)
            return
        self._repo.mark_read(rec.doc_id.value, uid)
        self._fill_reads(rec)