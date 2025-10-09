# documents/gui/main_view.py
"""
Pure GUI for the Documents module.

- All business logic is in `documents/gui/main_view_logic.py` (Controller).
- This view handles widgets, layout, event wiring only.

Stability updates:
- Robust reloading without triggering selection handlers (self._loading guard).
- Clear selection and focus safely before deleting/reinserting rows.
- Defensive inserts; avoid TclError "No item with that key" on race conditions.
- Stable sort keys; no mixed types.
- FIX: add _open_comment_detail() (double-click handler for comments).

New in this version:
- Status filter (Dropdown): Alle / Entwurf / Prüfung / Freigabe / Veröffentlicht / Obsolet
- "Nur aktive Workflows" checkbox (DRAFT / IN_REVIEW / APPROVAL)
- _reload() passes (status, active_only) through to controller.list_documents()
"""

from __future__ import annotations

import os
import sys
import subprocess
from typing import Optional, Dict, Any
from datetime import datetime

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

# i18n / App-Context -----------------------------------------------------------
try:
    from core.common.app_context import AppContext, T  # type: ignore
except Exception:
    class AppContext:  # type: ignore
        current_user: object | None = None
        @staticmethod
        def signature():
            raise RuntimeError("Signature API not available")
    def T(key: str) -> str:  # type: ignore
        return ""

# Settings ---------------------------------------------------------------------
try:
    from core.settings.logic.settings_manager import SettingsManager  # type: ignore
except Exception:
    class SettingsManager:  # type: ignore
        def get(self, section: str, key: str, default: Any = None) -> Any:
            return default

# Domain -----------------------------------------------------------------------
from documents.models.document_models import DocumentRecord, DocumentStatus  # type: ignore

# Controller / Logic -----------------------------------------------------------
from documents.gui.main_view_logic import DocumentsController, Assignments  # type: ignore

# Dialogs ----------------------------------------------------------------------
try:
    from documents.gui.dialogs.assign_roles_dialog import AssignRolesDialog  # type: ignore
except Exception:
    AssignRolesDialog = None  # type: ignore

try:
    from documents.gui.dialogs.metadata_dialog import MetadataDialog  # type: ignore
except Exception:
    MetadataDialog = None  # type: ignore

try:
    from documents.gui.dialogs.change_note_dialog import ChangeNoteDialog  # type: ignore
except Exception:
    ChangeNoteDialog = None  # type: ignore


class DocumentsView(ttk.Frame):
    """
    Tkinter view. GUI only; keeps logic in the controller.
    """
    _FEATURE_ID = "documents"

    # ------------------------------------------------------------------ init
    def __init__(self, parent: tk.Misc, *, settings_manager: SettingsManager) -> None:
        super().__init__(parent)

        self._sm = settings_manager
        self.ctrl = DocumentsController(settings_manager)
        self._init_error: Optional[str] = None

        # Guard flag to suppress selection handling during reload
        self._loading: bool = False

        try:
            self.ctrl.init()
        except Exception as ex:
            self._init_error = f"Initialization failed: {ex}"

        self._build_ui()
        self._reload()
        self._on_select()

    # --------------------------------------------------------------- UI build
    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        if self._init_error:
            ttk.Label(
                self,
                text=(T("documents.init_error") or "Module initialization problem: ") + str(self._init_error),
                foreground="#b00020",
                wraplength=780,
                justify="left",
            ).grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))

        header = ttk.Frame(self)
        header.grid(row=0 if not self._init_error else 1, column=0, sticky="ew", padx=12, pady=(12, 6))
        # allow many controls; last column stretches
        header.columnconfigure(10, weight=1)

        ttk.Label(header, text=(T("documents.title") or "Document Control"),
                  font=("Segoe UI", 16, "bold")).grid(row=0, column=0, sticky="w")

        # Search
        ttk.Label(header, text=(T("documents.filter.search") or "Search")).grid(row=0, column=1, padx=(12, 4))
        self.e_search = ttk.Entry(header, width=24); self.e_search.grid(row=0, column=2, sticky="w")
        ttk.Button(header, text=(T("common.search") or "Search"), command=self._reload)\
            .grid(row=0, column=3, sticky="w", padx=(6, 0))

        # Sort
        ttk.Label(header, text=(T("documents.filter.sort") or "Sortierung")).grid(row=0, column=4, padx=(12, 4), sticky="e")
        self.cb_sort = ttk.Combobox(header, width=22, state="readonly",
                                    values=[
                                        "Aktualisiert (neueste zuerst)",
                                        "Status (Workflow-Reihenfolge)",
                                        "Titel (A→Z)",
                                    ])
        self.cb_sort.grid(row=0, column=5, sticky="w")
        self.cb_sort.current(0)
        self.cb_sort.bind("<<ComboboxSelected>>", lambda e: self._reload())

        # Status filter (NEW)
        ttk.Label(header, text=(T("documents.filter.status") or "Status")).grid(row=0, column=6, padx=(12, 4), sticky="e")
        self.cb_status = ttk.Combobox(header, width=18, state="readonly",
                                      values=["Alle", "Entwurf", "Prüfung", "Freigabe", "Veröffentlicht", "Obsolet"])
        self.cb_status.grid(row=0, column=7, sticky="w")
        self.cb_status.current(0)
        self.cb_status.bind("<<ComboboxSelected>>", lambda e: self._reload())

        # Active workflows only (NEW)
        self.var_active = tk.BooleanVar(value=False)
        self.chk_active = ttk.Checkbutton(header, text=(T("documents.filter.active") or "Nur aktive Workflows"),
                                          variable=self.var_active, command=self._reload)
        self.chk_active.grid(row=0, column=8, padx=(12, 0), sticky="w")

        body = ttk.Panedwindow(self, orient="horizontal")
        body.grid(row=1 if not self._init_error else 2, column=0, sticky="nsew", padx=12, pady=6)

        # Left list
        left = ttk.Frame(body)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        ttk.Label(left, text=(T("documents.list") or "Documents")).grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.tree = ttk.Treeview(
            left,
            columns=("id", "title", "type", "status", "ver"),
            show="headings",
            selectmode="browse",
            height=18,
        )
        for c, w in [("id", 180), ("title", 260), ("type", 80), ("status", 120), ("ver", 70)]:
            self.tree.heading(c, text=c.upper()); self.tree.column(c, width=w, stretch=(c == "title"))
        self.tree.grid(row=1, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._on_select())

        list_btns = ttk.Frame(left); list_btns.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        list_btns.columnconfigure(99, weight=1)
        ttk.Button(list_btns, text=(T("documents.import") or "Import"), command=self._import_file)\
            .grid(row=0, column=0, padx=(0, 6))
        ttk.Button(list_btns, text=(T("documents.new_from_tpl") or "New from Template"), command=self._new_from_template)\
            .grid(row=0, column=1)
        ttk.Button(list_btns, text=(T("documents.edit_meta") or "Edit Metadata"), command=self._edit)\
            .grid(row=0, column=2, padx=(12, 0))
        self.btn_assign_roles = ttk.Button(list_btns, text=(T("documents.assign.roles") or "Zuständigkeiten…"),
                                           command=lambda: self._assign_roles(force=False))
        self.btn_assign_roles.grid(row=0, column=3, padx=(12, 0))

        # Right tabs
        right = ttk.Notebook(body); body.add(left, weight=1); body.add(right, weight=2)

        # Tab: Overview
        self.tab_overview = ttk.Frame(right); right.add(self.tab_overview, text=(T("documents.tab.overview") or "Overview"))
        self._build_overview(self.tab_overview)

        # Tab: Comments
        self.tab_comments = ttk.Frame(right); right.add(self.tab_comments, text=(T("documents.tab.comments") or "Comments"))
        self._build_comments(self.tab_comments)

        # Footer
        footer = ttk.Frame(self)
        footer.grid(row=2 if not self._init_error else 3, column=0, sticky="ew", padx=12, pady=(6, 12))

        self.btn_workflow = ttk.Button(footer, text=(T("documents.btn.workflow.start") or "Workflow starten"),
                                       command=self._toggle_workflow)
        self.btn_next = ttk.Button(footer, text=(T("documents.btn.to_review") or "Zur Prüfung einreichen"),
                                   command=self._next_step)
        self.btn_back_to_draft = ttk.Button(footer, text=(T("documents.btn.back_to_draft") or "Zurück zu Entwurf"),
                                            command=self._back_to_draft)
        self.btn_archive = ttk.Button(footer, text=(T("documents.btn.archive") or "Archivieren"),
                                      command=self._archive)
        self.btn_open = ttk.Button(footer, text=(T("documents.btn.open") or "Open"),
                                   command=self._open_current)
        self.btn_copy = ttk.Button(footer, text=(T("documents.btn.copy") or "Controlled Copy"),
                                   command=self._copy)

        self.btn_workflow.grid(row=0, column=0, padx=(0, 6))
        self.btn_next.grid(row=0, column=1, padx=(0, 6))
        self.btn_back_to_draft.grid(row=0, column=2, padx=(0, 6))
        self.btn_archive.grid(row=0, column=3, padx=(0, 6))
        self.btn_open.grid(row=0, column=4, padx=(0, 6))
        self.btn_copy.grid(row=0, column=5, padx=(0, 6))

    # --------------------------------------------------------------- tabs
    def _build_overview(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)
        r = 0

        ttk.Label(parent, text=(T("documents.ov.id") or "Document ID")).grid(row=r, column=0, sticky="w")
        self.l_id = ttk.Label(parent); self.l_id.grid(row=r, column=1, sticky="w"); r += 1

        ttk.Label(parent, text=(T("documents.ov.title") or "Title")).grid(row=r, column=0, sticky="w")
        self.l_title = ttk.Label(parent); self.l_title.grid(row=r, column=1, sticky="w"); r += 1

        ttk.Label(parent, text=(T("documents.ov.type") or "Type")).grid(row=r, column=0, sticky="w")
        self.l_type = ttk.Label(parent); self.l_type.grid(row=r, column=1, sticky="w"); r += 1

        ttk.Label(parent, text=(T("documents.ov.status") or "Status")).grid(row=r, column=0, sticky="w")
        self.l_status = ttk.Label(parent); self.l_status.grid(row=r, column=1, sticky="w"); r += 1

        ttk.Label(parent, text=(T("documents.ov.version") or "Version")).grid(row=r, column=0, sticky="w")
        self.l_ver = ttk.Label(parent); self.l_ver.grid(row=r, column=1, sticky="w"); r += 1

        ttk.Label(parent, text=(T("documents.ov.current") or "Current File")).grid(row=r, column=0, sticky="w")
        self.l_file = ttk.Label(parent); self.l_file.grid(row=r, column=1, sticky="w"); r += 1

        ttk.Separator(parent).grid(row=r, column=0, columnspan=2, sticky="ew", pady=(6, 6)); r += 1
        ttk.Label(parent, text="Editor (ausgeführt)").grid(row=r, column=0, sticky="w")
        self.l_exec_editor = ttk.Label(parent); self.l_exec_editor.grid(row=r, column=1, sticky="w"); r += 1

        ttk.Label(parent, text="Reviewer (ausgeführt)").grid(row=r, column=0, sticky="w")
        self.l_exec_reviewer = ttk.Label(parent); self.l_exec_reviewer.grid(row=r, column=1, sticky="w"); r += 1

        ttk.Label(parent, text="Publisher (ausgeführt)").grid(row=r, column=0, sticky="w")
        self.l_exec_publisher = ttk.Label(parent); self.l_exec_publisher.grid(row=r, column=1, sticky="w"); r += 1

        ttk.Label(parent, text="Editor Signature Date").grid(row=r, column=0, sticky="w")
        self.l_dt_editor = ttk.Label(parent); self.l_dt_editor.grid(row=r, column=1, sticky="w"); r += 1

        ttk.Label(parent, text="Reviewer Signature Date").grid(row=r, column=0, sticky="w")
        self.l_dt_reviewer = ttk.Label(parent); self.l_dt_reviewer.grid(row=r, column=1, sticky="w"); r += 1

        ttk.Label(parent, text="Publisher Signature Date").grid(row=r, column=0, sticky="w")
        self.l_dt_publisher = ttk.Label(parent); self.l_dt_publisher.grid(row=r, column=1, sticky="w"); r += 1

        ttk.Separator(parent).grid(row=r, column=0, columnspan=2, sticky="ew", pady=(6, 6)); r += 1
        meta_labels = [
            ("Description", "l_desc"),
            ("Document Type", "l_dtype"),
            ("Actual File Type", "l_actual_ftype"),
            ("Valid From / Review Due", "l_valid"),
            ("Last Modified", "l_lastmod"),
        ]
        self._meta_map: Dict[str, ttk.Label] = {}
        for caption, name in meta_labels:
            ttk.Label(parent, text=caption).grid(row=r, column=0, sticky="w")
            lab = ttk.Label(parent); lab.grid(row=r, column=1, sticky="w"); self._meta_map[name] = lab; r += 1

    def _build_comments(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1); parent.rowconfigure(0, weight=1)
        cols = ("author", "date", "text")
        self.tv_comments = ttk.Treeview(parent, columns=cols, show="headings", height=10)
        for c, cap in [("author", T("documents.col.author") or "Author"),
                       ("date", T("documents.col.date") or "Date"),
                       ("text", T("documents.col.text") or "Text")]:
            self.tv_comments.heading(c, text=cap)
        self.tv_comments.column("author", width=160); self.tv_comments.column("date", width=160)
        self.tv_comments.column("text", width=460)
        self.tv_comments.grid(row=0, column=0, sticky="nsew")

        # Doppelklick -> Detail
        self.tv_comments.bind("<Double-1>", self._open_comment_detail)

    # --------------------------------------------------------------- helpers
    @staticmethod
    def _ts(val: Any) -> float:
        """Stable float timestamp for sorting."""
        if val is None:
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        if hasattr(val, "timestamp"):
            try:
                return float(val.timestamp())
            except Exception:
                pass
        try:
            return float(datetime.fromisoformat(str(val).replace("Z", "+00:00")).timestamp())
        except Exception:
            return 0.0

    def _reload(self) -> None:
        if self._loading:
            return
        self._loading = True
        try:
            # Safely clear selection and focus before modifying the tree
            try:
                sel = self.tree.selection()
                if sel:
                    self.tree.selection_remove(sel)
            except Exception:
                pass
            try:
                self.tree.focus("")
            except Exception:
                pass

            # Delete all rows
            try:
                children = self.tree.get_children("")
                if children:
                    self.tree.delete(*children)
            except Exception:
                pass

            # Compose filters
            text = (self.e_search.get().strip() or None)

            status_obj = None
            try:
                sel_status = (self.cb_status.get() or "Alle").strip()
                mapping = {
                    "Alle": None,
                    "Entwurf": getattr(DocumentStatus, "DRAFT", None),
                    "Prüfung": getattr(DocumentStatus, "IN_REVIEW", None),
                    "Freigabe": getattr(DocumentStatus, "APPROVAL", None),
                    "Veröffentlicht": getattr(DocumentStatus, "PUBLISHED", None),
                    "Obsolet": getattr(DocumentStatus, "OBSOLETE", None),
                }
                status_obj = mapping.get(sel_status, None)
            except Exception:
                status_obj = None

            active_only = bool(getattr(self, "var_active", tk.BooleanVar(value=False)).get())

            # Load records (controller expected to accept status + active_only)
            records = self.ctrl.list_documents(text, status=status_obj, active_only=active_only)

            # Apply sort
            sort_sel = self.cb_sort.get() or ""
            if sort_sel.startswith("Status"):
                order = {
                    "DRAFT": 0, "IN_REVIEW": 1, "APPROVAL": 2,
                    "PUBLISHED": 3, "ARCHIVED": 4, "OBSOLETE": 4
                }
                records = sorted(
                    records,
                    key=lambda r: (order.get(getattr(r.status, "name", str(r.status)), 99),
                                   (r.title or "").lower())
                )
            elif sort_sel.startswith("Titel"):
                records = sorted(records, key=lambda r: (r.title or "").lower())
            else:
                records = sorted(records, key=lambda r: self._ts(getattr(r, "updated_at", None)), reverse=True)

            # Insert; ensure unique, valid iids
            seen: set[str] = set()
            for r in records:
                base_iid = str(getattr(r.doc_id, "value", r.doc_id))
                iid = base_iid
                i = 1
                while iid in seen:
                    iid = f"{base_iid}__{i}"
                    i += 1
                seen.add(iid)
                try:
                    self.tree.insert(
                        "", "end", iid=iid,
                        values=(base_iid, r.title, r.doc_type,
                                getattr(r.status, "name", str(r.status)),
                                self._display_version(r))
                    )
                except tk.TclError:
                    # Fallback: let Tk assign an iid automatically
                    try:
                        self.tree.insert(
                            "", "end",
                            values=(base_iid, r.title, r.doc_type,
                                    getattr(r.status, "name", str(r.status)),
                                    self._display_version(r))
                        )
                    except Exception:
                        continue

        except Exception as ex:
            messagebox.showerror("Documents", f"Load failed: {ex}", parent=self)
        finally:
            self._loading = False

    def _display_version(self, rec: DocumentRecord) -> str:
        ver = rec.version_label or ""
        try:
            major_s, minor_s = ver.split(".", 1)
            major, minor = int(major_s), int(minor_s)
        except Exception:
            return ver
        try:
            meta = self.ctrl.get_docx_meta(rec) or {}
            rev = int(meta.get("revision")) if meta.get("revision") is not None else None
        except Exception:
            rev = None
        if isinstance(rev, int) and rev >= 0:
            return f"{major}.{minor + rev}"
        return ver

    def _selected_record(self) -> Optional[DocumentRecord]:
        if self._loading:
            return None
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            # strip any suffix from iid
            return self.ctrl.get_document(sel[0].split("__", 1)[0])
        except Exception:
            return None

    def _on_select(self) -> None:
        if self._loading:
            return
        rec = self._selected_record()
        self._fill_overview(rec)
        self._fill_comments(rec)
        self._refresh_controls(rec)

    def _fill_overview(self, rec: Optional[DocumentRecord]) -> None:
        def _set(lbl: ttk.Label, val: str) -> None: lbl.configure(text=val)

        if not rec:
            for label in [getattr(self, n) for n in ("l_id","l_title","l_type","l_status","l_ver","l_file",
                                                      "l_exec_editor","l_exec_reviewer","l_exec_publisher",
                                                      "l_dt_editor","l_dt_reviewer","l_dt_publisher")]:
                _set(label, "")
            for lab in self._meta_map.values():
                _set(lab, "")
            return

        _set(self.l_id, rec.doc_id.value)
        _set(self.l_title, rec.title)
        _set(self.l_type, rec.doc_type)
        _set(self.l_status, getattr(rec.status, "name", str(rec.status)))
        _set(self.l_ver, self._display_version(rec))
        _set(self.l_file, rec.current_file_path or "-")

        exec_info: Dict[str, Any] = {}
        try:
            if hasattr(self.ctrl, "get_actual_actors"):
                exec_info = self.ctrl.get_actual_actors(rec) or {}
        except Exception:
            exec_info = {}

        _set(self.l_exec_editor, exec_info.get("editor") or "—")
        _set(self.l_exec_reviewer, exec_info.get("reviewer") or "—")
        _set(self.l_exec_publisher, exec_info.get("publisher") or "—")
        _set(self.l_dt_editor, exec_info.get("editor_dt") or "—")
        _set(self.l_dt_reviewer, exec_info.get("reviewer_dt") or "—")
        _set(self.l_dt_publisher, exec_info.get("publisher_dt") or "—")

        details: Dict[str, Any] = {}
        try:
            if hasattr(self.ctrl, "get_document_details"):
                details = self.ctrl.get_document_details(rec) or {}
        except Exception:
            details = {}

        _set(self._meta_map["l_desc"], details.get("description") or "—")
        _set(self._meta_map["l_dtype"], details.get("documenttype") or rec.doc_type or "—")
        path = rec.current_file_path or ""
        ftype = details.get("actual_filetype") or (os.path.splitext(path)[1][1:].upper() if path else "—")
        _set(self._meta_map["l_actual_ftype"], ftype)
        _set(self._meta_map["l_valid"], details.get("valid_by_date") or "—")
        _set(self._meta_map["l_lastmod"], details.get("last_modified") or getattr(rec, "updated_at", "") or "—")

    def _fill_comments(self, rec: Optional[DocumentRecord]) -> None:
        try:
            for i in self.tv_comments.get_children():
                self.tv_comments.delete(i)
        except Exception:
            pass
        if not rec:
            return
        repo = getattr(self.ctrl, "_repo", None)
        if not repo:
            return
        try:
            comments = repo.list_comments(rec.doc_id.value)
        except Exception:
            comments = []

        def preview(text: str, n: int = 20) -> str:
            text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
            return (text[:n] + ("…" if len(text) > n else "")).replace("\n", " ")

        for c in (comments or []):
            try:
                self.tv_comments.insert("", "end",
                                        values=(c.get("author"), c.get("date"), preview(c.get("text",""))))
            except Exception:
                continue

    # NEW: Double-click comment detail ----------------------------------------
    def _open_comment_detail(self, event=None) -> None:
        """Open a modal window showing the full comment text + basic meta."""
        if self._loading:
            return
        sel = self.tv_comments.selection()
        if not sel:
            return
        item = self.tv_comments.item(sel[0])
        vals = item.get("values") or []
        author = vals[0] if len(vals) > 0 else ""
        date = vals[1] if len(vals) > 1 else ""
        full_text = ""

        rec = self._selected_record()
        repo = getattr(self.ctrl, "_repo", None)

        # Try to resolve the full text from repository (match author+date)
        if repo and rec:
            try:
                for c in repo.list_comments(rec.doc_id.value):
                    if (c.get("author") == author) and (c.get("date") == date):
                        full_text = c.get("text") or ""
                        break
            except Exception:
                pass

        # Fallback: if not found, show preview text (3rd column)
        if not full_text and len(vals) > 2:
            full_text = str(vals[2])

        win = tk.Toplevel(self)
        win.title("Kommentar")
        win.geometry("680x420")
        frm = ttk.Frame(win, padding=12); frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=f"Author: {author or '—'}").pack(anchor="w")
        ttk.Label(frm, text=f"Date:   {date or '—'}").pack(anchor="w")
        txt = tk.Text(frm, wrap="word", height=16)
        txt.pack(fill="both", expand=True, pady=(8, 0))
        txt.insert("1.0", full_text or "(kein Text)")
        txt.configure(state="disabled")
        ttk.Button(frm, text="Schließen", command=win.destroy).pack(anchor="e", pady=(8,0))

    # --------------------------------------------------------------- actions
    def _refresh_controls(self, rec: Optional[DocumentRecord]) -> None:
        for btn in [self.btn_workflow, self.btn_next, self.btn_back_to_draft, self.btn_archive, self.btn_open, self.btn_copy]:
            btn.configure(state="disabled")
        self.btn_assign_roles.configure(state="disabled")

        if not rec:
            return

        state = self.ctrl.compute_controls_state(rec)

        self.btn_workflow.configure(text=(T("documents.btn.workflow.start") or "Workflow starten")
                                    if "start" in state.workflow_text.lower()
                                    else (T("documents.btn.workflow.abort") or "Workflow abbrechen"))
        self.btn_next.configure(text=state.next_text)

        self.btn_open.configure(state=("normal" if state.can_open else "disabled"))
        self.btn_copy.configure(state=("normal" if state.can_copy else "disabled"))
        self.btn_assign_roles.configure(state=("normal" if state.can_assign_roles else "disabled"))
        self.btn_archive.configure(state=("normal" if state.can_archive else "disabled"))
        self.btn_next.configure(state=("normal" if state.can_next else "disabled"))
        self.btn_back_to_draft.configure(state=("normal" if state.can_back_to_draft else "disabled"))
        self.btn_workflow.configure(state=("normal" if state.can_toggle_workflow else "disabled"))

    def _toggle_workflow(self) -> None:
        rec = self._selected_record()
        if not rec: return

        text = self.btn_workflow.cget("text").lower()
        if "start" in text or "starten" in text:
            ok = self.ctrl.start_workflow(rec, ensure_assignments=lambda: self._assign_roles(force=True))
            if not ok:
                messagebox.showinfo("Workflow", "Workflow nicht gestartet.", parent=self)
        else:
            ok, msg = self.ctrl.abort_workflow(
                rec,
                reason_provider=lambda: self._ask_reason(T("documents.reason.abort") or "Grund für Abbruch"),
                password_provider=lambda: simpledialog.askstring("Passwort", "Bitte Passwort bestätigen:", show="*", parent=self)
            )
            if not ok:
                messagebox.showerror("Workflow", msg or "Abbruch fehlgeschlagen.", parent=self)

        self._reload(); self._on_select()

    def _next_step(self) -> None:
        rec = self._selected_record()
        if not rec: return
        ok, msg = self.ctrl.forward_transition(
            rec,
            ask_reason=lambda: self._ask_reason(self.btn_next.cget("text")),
            sign_pdf=self._interactive_sign
        )
        if not ok:
            messagebox.showerror("Workflow", msg or "Schritt fehlgeschlagen.", parent=self)
        self._reload(); self._on_select()

    def _back_to_draft(self) -> None:
        rec = self._selected_record()
        if not rec: return
        ok, msg = self.ctrl.backward_to_draft(
            rec,
            ask_reason=lambda: self._ask_reason(T("documents.reason.back_to_draft") or "Grund – Zurück zu Entwurf")
        )
        if not ok:
            messagebox.showerror("Workflow", msg or "Rücksprung fehlgeschlagen.", parent=self)
        self._reload(); self._on_select()

    def _archive(self) -> None:
        rec = self._selected_record()
        if not rec: return
        ok, msg = self.ctrl.archive(
            rec,
            ask_reason=lambda: self._ask_reason(T("documents.reason.archive") or "Grund – Archivieren")
        )
        if not ok:
            messagebox.showerror("Archivieren", "Archivierung fehlgeschlagen.", parent=self)
        self._reload(); self._on_select()

    def _assign_roles(self, force: bool = False) -> bool:
        rec = self._selected_record()
        if not rec: return False

        users = self.ctrl.list_users_for_dialog()
        if not users:
            messagebox.showerror("Users", "Keine Benutzerliste verfügbar (Usermanagement/RBAC).", parent=self)
            return False

        current = self.ctrl.get_assignees(rec.doc_id.value) or {}

        while True:
            try:
                dlg = AssignRolesDialog(self, users=users, current=current)  # type: ignore
            except Exception as ex:
                messagebox.showerror("Assign Roles", f"Dialogfehler: {ex}", parent=self)
                return False

            self.wait_window(dlg)
            result = getattr(dlg, "result", None)
            if not result:
                return False  # Abgebrochen

            authors = list(result.get("AUTHOR") or [])
            reviewers = list(result.get("REVIEWER") or [])
            approvers = list(result.get("APPROVER") or [])

            ok, msg = self.ctrl.validate_assignments(reviewers, approvers)
            if not ok:
                messagebox.showerror("Zuständigkeiten", msg, parent=self)
                current = {"AUTHOR": authors, "REVIEWER": reviewers, "APPROVER": approvers}
                continue

            self.ctrl.set_assignees(rec.doc_id.value,
                                    Assignments(authors=authors, reviewers=reviewers, approvers=approvers))
            self._reload(); self._on_select()
            return True

    # --------------------------------------------------------------- utilities
    def _ask_reason(self, title: str) -> Optional[str]:
        if ChangeNoteDialog:
            dlg = ChangeNoteDialog(self, title)  # type: ignore
            self.wait_window(dlg)
            reason = (getattr(dlg, "result", "") or "").strip()
            return reason or None
        return simpledialog.askstring("Reason", title, parent=self)

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
        if os.path.isfile(pdf_path):
            return pdf_path
        return None

    def _open_current(self) -> None:
        rec = self._selected_record()
        if not rec or not rec.current_file_path:
            return
        path = rec.current_file_path
        try:
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as ex:
            messagebox.showerror(title=(T("documents.open.error") or "Open failed"), message=str(ex), parent=self)

    # ----------------------------------------------------------- repo passthroughs
    def _import_file(self) -> None:
        repo = getattr(self.ctrl, "_repo", None)
        if not repo:
            return
        path = filedialog.askopenfilename(parent=self, title=(T("documents.import.title") or "Import Document"),
                                          filetypes=[("DOCX", "*.docx"), ("All", "*.*")])
        if not path:
            return
        rec = repo.create_from_file(title=None, doc_type="SOP", user_id=self.ctrl.current_user_id(), src_file=path)
        messagebox.showinfo(title=(T("documents.import.ok") or "Imported"),
                            message=(T("documents.import.msg") or "Document created: ") + rec.doc_id.value, parent=self)
        self._reload()

    def _new_from_template(self) -> None:
        repo = getattr(self.ctrl, "_repo", None)
        if not repo:
            return
        import os as _os
        proj_root = _os.path.abspath(_os.path.join(_os.getcwd()))
        tdir = _os.path.join(proj_root, "templates")
        if not _os.path.isdir(tdir):
            messagebox.showwarning(title=(T("documents.tpl.missing.title") or "No templates"),
                                   message=(T("documents.tpl.missing.msg") or "Folder not found: ") + tdir, parent=self)
            return
        path = filedialog.askopenfilename(parent=self, title=(T("documents.tpl.choose") or "Choose template"),
                                          initialdir=tdir, filetypes=[("DOCX", "*.docx"), ("All", "*.*")])
        if not path:
            return
        rec = repo.create_from_file(title=None, doc_type="SOP", user_id=self.ctrl.current_user_id(), src_file=path)
        messagebox.showinfo(title=(T("documents.tpl.created") or "Document created"),
                            message=(T("documents.tpl.created.msg") or "Created from template: ") + rec.doc_id.value,
                            parent=self)
        self._reload()

    def _edit(self) -> None:
        repo = getattr(self.ctrl, "_repo", None)
        if not repo:
            return
        rec = self._selected_record()
        if not rec:
            return
        if not MetadataDialog:
            messagebox.showinfo("Metadata", "Metadata dialog not available.", parent=self)
            return
        allowed = [t.strip() for t in str(self._sm.get(self._FEATURE_ID, "allowed_types", "SOP,WI,FB,CL")).split(",")]
        dlg = MetadataDialog(self, rec, allowed_types=allowed)  # type: ignore
        self.wait_window(dlg)
        result = getattr(dlg, "result", None)
        if result:
            repo.update_metadata(result, self.ctrl.current_user_id())
            self._reload(); self._on_select()

    def _copy(self) -> None:
        repo = getattr(self.ctrl, "_repo", None)
        if not repo:
            return
        rec = self._selected_record()
        if not rec or rec.status != DocumentStatus.PUBLISHED:
            return
        dest_dir = filedialog.askdirectory(parent=self, title=(T("documents.copy.choose_dest") or "Choose destination"))
        if not dest_dir:
            return
        try:
            out = repo.copy_to_destination(rec.doc_id.value, dest_dir)
            if out:
                messagebox.showinfo(title=(T("documents.copy.ok") or "Copy created"),
                                    message=(T("documents.copy.done") or "Copy created at: ") + out, parent=self)
        except Exception as ex:
            messagebox.showerror("Copy", str(ex), parent=self)
