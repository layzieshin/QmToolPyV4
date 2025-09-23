"""
Dokumentenlenkung – aufgeräumtes UI:
- Vertikal geteilte Ansicht (links Liste, rechts Tabs: Übersicht, Metadaten, Kommentare, Lesestatus)
- CTA „Workflow starten/fortsetzen“ (Rollenwahl bei Start integriert)
- Separater Button „Nächster Schritt“ (statusabhängige Beschriftung)
- „Zurück zu Entwurf“ (signaturpflichtig)
- Jeder Statuswechsel signiert über SignatureAPI (Repository kümmert sich um Stempel)
- Optionales Check-in/Check-out (per Setting 'enable_checkout')
"""

from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Set, Tuple, Any

# AppContext (nicht verändern!)
try:
    from core.common.app_context import AppContext
except Exception:
    class AppContext:
        app_storage_dir: str | None = None
        current_user: object | None = None
        @staticmethod
        def T(label: str, default: str = "") -> str: return default
        translate = T

from documents.gui.i18n import tr
from core.settings.logic.settings_manager import SettingsManager

# Models/Logic
from documents.models.document_models import DocumentRecord, DocumentStatus
from documents.logic.repository import DocumentsRepository, RepoConfig
from documents.logic.workflow_engine import WorkflowEngine
from documents.logic.permissions import ModulePermissions
from documents.logic.rbac_service import RBACService

# Dialoge
from documents.gui.dialogs.metadata_dialog import MetadataDialog
from documents.gui.dialogs.change_note_dialog import ChangeNoteDialog
from documents.gui.dialogs.assign_roles_dialog import AssignRolesDialog


class DocumentsView(ttk.Frame):
    _FEATURE_ID = "documents"

    def __init__(self, parent: tk.Misc, *, settings_manager: SettingsManager) -> None:
        super().__init__(parent)
        self._sm = settings_manager
        self._wf = WorkflowEngine()
        self._perms = ModulePermissions(self._sm)

        self._repo = DocumentsRepository(self._load_repo_cfg())
        self._rbac = RBACService(self._repo._cfg["db_path"], self._sm)

        self._enable_checkout = bool(int(self._sm.get(self._FEATURE_ID, "enable_checkout", 0)))

        # Layout
        self.columnconfigure(0, weight=1); self.rowconfigure(1, weight=1)

        header = ttk.Frame(self); header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        header.columnconfigure(3, weight=1)
        ttk.Label(header, text=tr("documents.title", "Document Control"), font=("Segoe UI", 16, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text=tr("documents.filter.search", "Search")).grid(row=0, column=1, padx=(12,4))
        self.e_search = ttk.Entry(header, width=24); self.e_search.grid(row=0, column=2, sticky="w")
        ttk.Button(header, text=tr("common.search", "Search"), command=self._reload).grid(row=0, column=3, sticky="w", padx=(6,0))

        body = ttk.Panedwindow(self, orient="horizontal"); body.grid(row=1, column=0, sticky="nsew", padx=12, pady=6)

        # Linke Liste
        left = ttk.Frame(body)
        left.columnconfigure(0, weight=1); left.rowconfigure(1, weight=1)
        ttk.Label(left, text=tr("documents.list", "Documents")).grid(row=0, column=0, sticky="w", pady=(0,4))
        self.tree = ttk.Treeview(left, columns=("id","title","type","status","ver"), show="headings", selectmode="browse", height=18)
        for c, w in [("id", 180), ("title", 260), ("type", 80), ("status", 100), ("ver", 60)]:
            self.tree.heading(c, text=c.upper()); self.tree.column(c, width=w, stretch=True if c in ("title",) else False)
        self.tree.grid(row=1, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._on_select())

        list_btns = ttk.Frame(left); list_btns.grid(row=2, column=0, sticky="ew", pady=(6,0))
        list_btns.columnconfigure(99, weight=1)
        ttk.Button(list_btns, text=tr("documents.btn.import", "Import"), command=self._import).grid(row=0, column=0, padx=(0,6))
        ttk.Button(list_btns, text="Neu aus Vorlage", command=self._new_from_template).grid(row=0, column=1, padx=(0,6))
        self.btn_out = ttk.Button(list_btns, text=tr("documents.btn.checkout", "Check-out"), command=self._checkout)
        self.btn_in  = ttk.Button(list_btns, text=tr("documents.btn.checkin", "Check-in"), command=self._checkin)
        if self._enable_checkout:
            self.btn_out.grid(row=0, column=2, padx=(0,6))
            self.btn_in.grid(row=0, column=3, padx=(0,6))

        # Rechte Seite: Tabs
        right = ttk.Frame(body)
        right.columnconfigure(0, weight=1); right.rowconfigure(0, weight=1)
        self.tabs = ttk.Notebook(right); self.tabs.grid(row=0, column=0, sticky="nsew")

        # Tab Übersicht
        self.tab_over = ttk.Frame(self.tabs); self.tabs.add(self.tab_over, text=tr("documents.tab.overview", "Übersicht"))
        self._build_overview(self.tab_over)

        # Tab Metadaten
        self.tab_meta = ttk.Frame(self.tabs); self.tabs.add(self.tab_meta, text=tr("documents.tab.meta", "Metadaten"))
        self._build_meta(self.tab_meta)

        # Tab Kommentare
        self.tab_comments = ttk.Frame(self.tabs); self.tabs.add(self.tab_comments, text=tr("documents.tab.comments", "Kommentare"))
        self._build_comments(self.tab_comments)

        # Tab Lesestatus
        self.tab_reads = ttk.Frame(self.tabs); self.tabs.add(self.tab_reads, text=tr("documents.tab.reads", "Lesestatus"))
        self._build_reads(self.tab_reads)

        body.add(left, weight=1); body.add(right, weight=2)

        self._reload()
        self._on_select()

    # ---- UI-Bau --------------------------------------------------------------
    def _build_overview(self, host: ttk.Frame) -> None:
        host.columnconfigure(1, weight=1)
        r = 0
        ttk.Label(host, text=tr("documents.ov.id", "ID:")).grid(row=r, column=0, sticky="w"); self.l_id = ttk.Label(host); self.l_id.grid(row=r, column=1, sticky="w"); r += 1
        ttk.Label(host, text=tr("documents.ov.title", "Titel:")).grid(row=r, column=0, sticky="w"); self.l_title = ttk.Label(host); self.l_title.grid(row=r, column=1, sticky="w"); r += 1
        ttk.Label(host, text=tr("documents.ov.type", "Typ:")).grid(row=r, column=0, sticky="w"); self.l_type = ttk.Label(host); self.l_type.grid(row=r, column=1, sticky="w"); r += 1
        ttk.Label(host, text=tr("documents.ov.status", "Status:")).grid(row=r, column=0, sticky="w"); self.l_status = ttk.Label(host); self.l_status.grid(row=r, column=1, sticky="w"); r += 1
        ttk.Label(host, text=tr("documents.ov.version", "Version:")).grid(row=r, column=0, sticky="w"); self.l_ver = ttk.Label(host); self.l_ver.grid(row=r, column=1, sticky="w"); r += 1
        ttk.Label(host, text=tr("documents.ov.file", "Datei:")).grid(row=r, column=0, sticky="w"); self.l_file = ttk.Label(host); self.l_file.grid(row=r, column=1, sticky="w"); r += 1

        # Aktionen
        btns = ttk.Frame(host); btns.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(8,0))
        btns.columnconfigure(5, weight=1)
        self.btn_workflow = ttk.Button(btns, text="Workflow starten", command=self._cta_workflow)
        self.btn_next     = ttk.Button(btns, text="Nächster Schritt", command=self._next_step)
        self.btn_back_to_draft = ttk.Button(btns, text="Zurück zu Entwurf", command=self._back_to_draft)
        self.btn_open = ttk.Button(btns, text=tr("documents.btn.open", "Open"), command=self._open_current)
        self.btn_copy = ttk.Button(btns, text=tr("documents.btn.copy", "Controlled copy"), command=self._copy)
        self.btn_workflow.grid(row=0, column=0, padx=(0,6))
        self.btn_next.grid(row=0, column=1, padx=(0,6))
        self.btn_back_to_draft.grid(row=0, column=2, padx=(0,6))
        self.btn_open.grid(row=0, column=3, padx=(0,6))
        self.btn_copy.grid(row=0, column=4, padx=(0,6))

    def _build_meta(self, host: ttk.Frame) -> None:
        host.columnconfigure(1, weight=1)
        self.txt_meta = tk.Text(host, height=14, wrap="word")
        self.txt_meta.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=(0,0), pady=(0,6))
        host.rowconfigure(0, weight=1)
        ttk.Button(host, text=tr("documents.btn.edit", "Edit"), command=self._edit).grid(row=1, column=0, sticky="w")

    def _build_comments(self, host: ttk.Frame) -> None:
        host.columnconfigure(0, weight=1); host.rowconfigure(0, weight=1)
        cols = ("version","author","date","text")
        self.tv_comments = ttk.Treeview(host, columns=cols, show="headings", height=12, selectmode="browse")
        for c, w in [("version",80),("author",160),("date",140),("text",600)]:
            self.tv_comments.heading(c, text=c.upper()); self.tv_comments.column(c, width=w, anchor="w", stretch=True if c=="text" else False)
        self.tv_comments.grid(row=0, column=0, sticky="nsew")
        ttk.Label(host, text=tr("documents.comments.hint", "Kommentare stammen aus dem Word-Dokument (Review-Kommentare).")).grid(row=1, column=0, sticky="w", pady=(4,0))

    def _build_reads(self, host: ttk.Frame) -> None:
        host.columnconfigure(0, weight=1); host.rowconfigure(0, weight=1)
        cols = ("version","user","read_at")
        self.tv_reads = ttk.Treeview(host, columns=cols, show="headings", height=12, selectmode="browse")
        for c, w in [("version",80),("user",240),("read_at",160)]:
            self.tv_reads.heading(c, text=c.upper()); self.tv_reads.column(c, width=w, anchor="w")
        self.tv_reads.grid(row=0, column=0, sticky="nsew")
        ttk.Button(host, text="Ich habe gelesen", command=self._mark_read).grid(row=1, column=0, sticky="e", pady=(6,0))

    # ---- Repo-Config ---------------------------------------------------------
    def _load_repo_cfg(self) -> RepoConfig:
        dflt_root = os.path.join(getattr(AppContext, "app_storage_dir", os.path.join(os.getcwd(),"data")), "documents_repo")
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
            watermark_copy=str(get("watermark_copy", "KONTROLLIERTE KOPIE"))
        )

    # ---- Helpers -------------------------------------------------------------
    def _current_user(self):
        return getattr(AppContext, "current_user", None)

    def _current_uid(self) -> Optional[str]:
        u = self._current_user()
        return getattr(u, "id", None) if u else None

    def _display_name_for_user_id(self, user_id: Optional[str]) -> str:
        if not user_id: return ""
        um = getattr(AppContext, "user_manager", None)
        if not um: return str(user_id)
        candidates = ["get_user_by_id", "get_user", "get", "find_by_id", "find_user", "load"]
        user_obj: Any = None
        for m in candidates:
            if hasattr(um, m):
                try:
                    user_obj = getattr(um, m)(user_id)
                    if user_obj: break
                except Exception: continue
        def _g(o: Any, *names: str) -> Optional[str]:
            for n in names:
                try:
                    if isinstance(o, dict) and n in o and o[n]:
                        return str(o[n])
                    v = getattr(o, n, None)
                    if v: return str(v)
                except Exception: pass
            return None
        return _g(user_obj, "full_name", "name", "display_name") or _g(user_obj, "username") or _g(user_obj, "email") or str(user_id)

    def _selected_record(self) -> Optional[DocumentRecord]:
        sel = self.tree.selection()
        if not sel:
            return None
        return self._repo.get(sel[0])

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

    # ---- Fillers -------------------------------------------------------------
    def _fill_overview(self, rec: Optional[DocumentRecord]) -> None:
        if not rec:
            for l in [self.l_id, self.l_title, self.l_type, self.l_status, self.l_ver, self.l_file]:
                l.configure(text="")
            for b in [self.btn_workflow, self.btn_next, self.btn_back_to_draft, self.btn_open, self.btn_copy]:
                b.configure(state="disabled")
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
        if not rec: return
        for c in self._repo.list_comments(rec.doc_id.value):
            self.tv_comments.insert("", "end", values=(c.get("version_label",""), c.get("author",""), c.get("date",""), c.get("text","")))

    def _fill_reads(self, rec: Optional[DocumentRecord]) -> None:
        self.tv_reads.delete(*self.tv_reads.get_children())
        if not rec: return
        for r in self._repo.list_reads(rec.doc_id.value):
            self.tv_reads.insert("", "end", values=(r["version_label"], r["user_id"], r["read_at"]))

    # ---- Controls ------------------------------------------------------------
    def _refresh_controls(self, rec: Optional[DocumentRecord]) -> None:
        # Deaktivieren
        for w in [self.btn_workflow, self.btn_next, self.btn_back_to_draft, self.btn_open, self.btn_copy]:
            w.configure(state="disabled")
        if not rec:
            return

        # Open/Copy
        if rec.current_file_path: self.btn_open.configure(state="normal")
        if rec.status in {DocumentStatus.PUBLISHED, DocumentStatus.OBSOLETE}: self.btn_copy.configure(state="normal")

        # Texte & Aktivierung nach Status
        if rec.status == DocumentStatus.DRAFT:
            self.btn_workflow.configure(text="Workflow starten", state="normal")
            self.btn_next.configure(text="In Prüfung geben", state="normal")
            self.btn_back_to_draft.configure(state="disabled")
        elif rec.status == DocumentStatus.IN_REVIEW:
            self.btn_workflow.configure(text="Workflow fortsetzen", state="normal")
            self.btn_next.configure(text="Freigabe anfordern", state="normal")
            self.btn_back_to_draft.configure(state="normal")
        elif rec.status == DocumentStatus.APPROVAL:
            self.btn_workflow.configure(text="Workflow fortsetzen", state="normal")
            self.btn_next.configure(text="Veröffentlichen", state="normal")
            self.btn_back_to_draft.configure(state="normal")
        else:
            # PUBLISHED / OBSOLETE – kein aktiver Workflow
            self.btn_workflow.configure(text="Kein aktiver Workflow", state="disabled")
            self.btn_next.configure(text="Nächster Schritt", state="disabled")
            self.btn_back_to_draft.configure(state="normal" if rec.status != DocumentStatus.DRAFT else "disabled")

        # Check-in/out
        if self._enable_checkout:
            self.btn_out.configure(state=("normal" if (rec.locked_by is None) else "disabled"))
            self.btn_in.configure(state=("normal" if (rec.locked_by is not None) else "disabled"))

    # ---- Signature helper (Reason only; Stempel macht Repo via API) ----------
    def _ask_reason(self, title: str) -> Optional[str]:
        dlg = ChangeNoteDialog(self, title)
        self.wait_window(dlg)
        reason = (dlg.result or "").strip()
        return reason or None

    # ---- Aktionen ------------------------------------------------------------
    def _import(self) -> None:
        path = filedialog.askopenfilename(parent=self, title=tr("documents.import.file", "Choose a document"),
                                          filetypes=[("Documents", "*.pdf *.docx *.xlsx *.pptx *.txt"), ("All", "*.*")])
        if not path:
            return
        rec = self._repo.create_from_file(title=None, doc_type="SOP", user_id=self._current_uid(), src_file=path)
        messagebox.showinfo(title=tr("documents.import.ok", "Imported"),
                            message=tr("documents.import.msg", "Document created: ") + rec.doc_id.value, parent=self)
        self._reload()

    def _new_from_template(self) -> None:
        proj_root = os.path.abspath(os.path.join(os.getcwd()))
        tdir = os.path.join(proj_root, "templates")
        if not os.path.isdir(tdir):
            messagebox.showwarning(title="No templates", message=f"Folder not found:\n{tdir}", parent=self); return
        path = filedialog.askopenfilename(parent=self, title="Choose template (*.docx)", initialdir=tdir,
                                          filetypes=[("Word template", "*.docx")])
        if not path:
            return
        base = os.path.splitext(os.path.basename(path))[0]
        dlg = ChangeNoteDialog(self, "Neues Dokument – ID und Titel (Format: A02VA001_Titel)")
        self.wait_window(dlg)
        name = (dlg.result or "").strip()
        if name and "_" in name:
            target_id, title = name.split("_", 1)
        else:
            target_id, title = None, base
        rec = self._repo.create_from_template(template_path=path, target_id=target_id, title=title, doc_type="SOP",
                                              user_id=self._current_uid())
        messagebox.showinfo(title="Created", message=f"Document created: {rec.doc_id.value}", parent=self)
        self._reload()

    def _checkout(self) -> None:
        if not self._enable_checkout: return
        rec = self._selected_record()
        if not rec: return
        ok = self._repo.check_out(rec.doc_id.value, self._current_uid() or "")
        if not ok:
            messagebox.showwarning(title=tr("documents.locked", "Locked"),
                                   message=tr("documents.locked.msg", "Document is already checked-out."), parent=self)
        self._reload()

    def _checkin(self) -> None:
        if not self._enable_checkout: return
        rec = self._selected_record()
        if not rec: return
        path = filedialog.askopenfilename(parent=self, title=tr("documents.checkin.file", "Choose updated file (optional)"),
                                          filetypes=[("Documents", "*.pdf *.docx *.xlsx *.pptx *.txt"), ("All", "*.*")])
        reason = self._ask_reason(tr("documents.checkin.note", "Change note")) or ""
        self._repo.check_in(rec.doc_id.value, self._current_uid() or "", path or None, reason)
        self._reload()

    # ---- Workflow ------------------------------------------------------------
    def _ensure_assignments(self, doc_id: str) -> bool:
        """Beim Start: Reviewer/Approver erzwingen; ggf. Dialog öffnen."""
        ass = self._repo.get_assignees(doc_id)
        need = (not ass.get("REVIEWER")) or (not ass.get("APPROVER"))
        if not need:
            return True
        users = self._rbac.list_users()
        dlg = AssignRolesDialog(self, users=users, current=ass)
        self.wait_window(dlg)
        if getattr(dlg, "result", None):
            self._repo.set_assignees(doc_id,
                                     authors=dlg.result.get("AUTHOR"),
                                     reviewers=dlg.result.get("REVIEWER") or [],
                                     approvers=dlg.result.get("APPROVER") or [])
            return True
        return False

    def _cta_workflow(self) -> None:
        rec = self._selected_record()
        if not rec: return
        uid = self._current_uid() or ""
        if rec.status == DocumentStatus.DRAFT:
            # Workflow START: Rollen zuweisen integrieren
            if not self._ensure_assignments(rec.doc_id.value):
                return
            # optional: sofortige Prüfungseinleitung über Next-Step (lassen Button für Klarheit)
            messagebox.showinfo("Workflow", "Rollen gesetzt. Du kannst jetzt „In Prüfung geben“.", parent=self)
        else:
            # Fortsetzen = Hinweis, dass der „Nächster Schritt“-Button benutzt wird
            messagebox.showinfo("Workflow", "Nutze „Nächster Schritt“, um fortzufahren.", parent=self)

    def _next_step(self) -> None:
        rec = self._selected_record()
        if not rec: return
        uid = self._current_uid() or ""

        if rec.status == DocumentStatus.DRAFT:
            # In Prüfung geben
            if not self._ensure_assignments(rec.doc_id.value):
                return
            # Prüf-PDF sicherstellen
            self._repo.generate_review_pdf(rec.doc_id.value)
            reason = self._ask_reason("Begründung – in Prüfung geben")
            if not reason: return
            # Signatur protokollieren & stempeln (Repository ruft SignatureAPI)
            self._repo.record_signature(rec.doc_id.value, step="submit_review", user_id=uid, reason=reason, signature_png=None)
            self._repo.set_status(rec.doc_id.value, DocumentStatus.IN_REVIEW, uid, reason)

        elif rec.status == DocumentStatus.IN_REVIEW:
            # Freigabe anfordern
            reason = self._ask_reason("Begründung – Freigabe anfordern")
            if not reason: return
            self._repo.record_signature(rec.doc_id.value, step="request_approval", user_id=uid, reason=reason, signature_png=None)
            self._repo.set_status(rec.doc_id.value, DocumentStatus.APPROVAL, uid, reason)

        elif rec.status == DocumentStatus.APPROVAL:
            # Veröffentlichen (PDF mit Versionssuffix)
            self._repo.export_pdf_with_version_suffix(rec.doc_id.value)
            reason = self._ask_reason("Begründung – Veröffentlichen")
            if not reason: return
            self._repo.record_signature(rec.doc_id.value, step="publish", user_id=uid, reason=reason, signature_png=None)
            self._repo.set_status(rec.doc_id.value, DocumentStatus.PUBLISHED, uid, reason)

        self._reload()
        self._on_select()

    def _back_to_draft(self) -> None:
        rec = self._selected_record()
        if not rec: return
        uid = self._current_uid() or ""
        if not messagebox.askyesno(title="Zurück zu Entwurf", message="Wirklich in den Entwurfsstatus zurücksetzen?", parent=self):
            return
        reason = self._ask_reason("Begründung – Zurück zu Entwurf")
        if not reason: return
        self._repo.record_signature(rec.doc_id.value, step="back_to_draft", user_id=uid, reason=reason, signature_png=None)
        self._repo.set_status(rec.doc_id.value, DocumentStatus.DRAFT, uid, reason)
        self._reload(); self._on_select()

    # ---- Sonstiges -----------------------------------------------------------
    def _copy(self) -> None:
        rec = self._selected_record()
        if not rec: return
        out = self._repo.make_controlled_copy(rec.doc_id.value)
        if out:
            messagebox.showinfo(title=tr("documents.copy.ok", "Controlled copy"),
                                message=tr("documents.copy.path", "File: ") + out, parent=self)

    def _open_current(self) -> None:
        rec = self._selected_record()
        if not rec or not rec.current_file_path: return
        path = rec.current_file_path
        try:
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                import subprocess; subprocess.Popen(["open", path])
            else:
                import subprocess; subprocess.Popen(["xdg-open", path])
        except Exception as ex:
            messagebox.showerror(title="Open error", message=str(ex), parent=self)

    def _edit(self) -> None:
        rec = self._selected_record()
        if not rec: return
        types = [t.strip() for t in str(self._sm.get(self._FEATURE_ID, "allowed_types", "SOP,WI,FB,CL")).split(",")]
        dlg = MetadataDialog(self, rec, allowed_types=types)
        if getattr(dlg, "result", None):
            self._repo.update_metadata(dlg.result, self._current_uid())
            self._reload(); self._on_select()

    def _mark_read(self) -> None:
        rec = self._selected_record()
        if not rec: return
        uid = self._current_uid()
        if not uid:
            messagebox.showwarning(title="Nicht angemeldet", message="Kein aktueller Benutzer.", parent=self); return
        self._repo.mark_read(rec.doc_id.value, uid)
        self._fill_reads(rec)
