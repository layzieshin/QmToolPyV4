"""
DocumentsView – main list/detail UI for the Documents feature.

This file is UI-only (SRP). All business logic lives in documents.gui.main_view_logic
and documents.logic.repository. The view:
- builds the list, details, comments UI
- collects user input (filters, dialogs)
- delegates actions to the controller (DocumentsController)
- reacts to state by (de)activating buttons & labels
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from typing import Any, Dict, Optional, List, Tuple

# Core services / i18n
from core.common.app_context import AppContext, T  # type: ignore
from core.settings.logic.settings_manager import SettingsManager  # type: ignore

# Models
from documents.models.document_models import DocumentRecord, DocumentStatus  # type: ignore

# Controller / Logic
from documents.gui.main_view_logic import DocumentsController, Assignments  # type: ignore

# Dialogs (optional – degrade gracefully if missing)
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

        self._rows: Dict[str, DocumentRecord] = {}
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
                text=(T("documents.init_error") or "Problem bei der Modulinitialisierung: ") + str(self._init_error),
                foreground="#b00020",
                wraplength=780,
                justify="left",
            ).grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))

        header = ttk.Frame(self)
        header.grid(row=0 if not self._init_error else 1, column=0, sticky="ew", padx=12, pady=(12, 6))
        header.columnconfigure(10, weight=1)

        ttk.Label(header, text=(T("documents.title") or "Document Control"),
                  font=("Segoe UI", 16, "bold")).grid(row=0, column=0, sticky="w")

        # Search
        ttk.Label(header, text=(T("documents.filter.search") or "Suche")).grid(row=0, column=1, padx=(12, 4))
        self.e_search = ttk.Entry(header, width=28)
        self.e_search.grid(row=0, column=2, sticky="w")
        ttk.Button(header, text=(T("common.search") or "Suchen"), command=self._reload)\
            .grid(row=0, column=3, sticky="w", padx=(6, 0))

        # Status filter
        ttk.Label(header, text=(T("documents.filter.status") or "Status")).grid(row=0, column=4, padx=(16, 4))
        self.cb_status = ttk.Combobox(
            header, state="readonly", width=16,
            values=[
                T("documents.status.all") or "Alle",
                T("documents.status.draft") or "Entwurf",
                T("documents.status.review") or "Prüfung",
                T("documents.status.approval") or "Freigabe",
                T("documents.status.published") or "Veröffentlicht",
                T("documents.status.obsolete") or "Obsolet",
            ],
        )
        self.cb_status.grid(row=0, column=5, sticky="w")
        self.cb_status.current(0)
        self.cb_status.bind("<<ComboboxSelected>>", lambda e: self._reload())

        # Active workflows only
        self.var_active_only = tk.BooleanVar(value=False)
        self.chk_active_only = ttk.Checkbutton(
            header,
            text=T("documents.filter.active") or "Nur aktive Workflows",
            variable=self.var_active_only,
            command=self._reload,
        )
        self.chk_active_only.grid(row=0, column=6, padx=(16, 0))

        # Sort
        ttk.Label(header, text=(T("documents.filter.sort") or "Sortierung")).grid(row=0, column=7, padx=(16, 4))
        self.cb_sort = ttk.Combobox(
            header, width=26, state="readonly",
            values=[
                "Aktualisiert (neueste zuerst)",
                "Status (Workflow-Reihenfolge)",
                "Titel (A→Z)",
            ],
        )
        self.cb_sort.grid(row=0, column=8, sticky="w")
        self.cb_sort.current(0)
        self.cb_sort.bind("<<ComboboxSelected>>", lambda e: self._reload())

        # Split
        body = ttk.Panedwindow(self, orient="horizontal")
        body.grid(row=1 if not self._init_error else 2, column=0, sticky="nsew", padx=12, pady=(4, 12))

        # Left: list
        left = ttk.Frame(body)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)
        body.add(left, weight=1)

        # Toolbar above list
        listbar = ttk.Frame(left)
        listbar.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ttk.Button(listbar, text=T("documents.btn.new_from_tpl") or "Neu aus Vorlage", command=self._new_from_template)\
            .pack(side="left")
        ttk.Button(listbar, text=T("documents.btn.import") or "Importieren", command=self._import_file)\
            .pack(side="left", padx=(6, 0))
        ttk.Button(listbar, text=T("documents.btn.edit_meta") or "Metadaten", command=self._edit)\
            .pack(side="left", padx=(6, 0))

        # Tree/list
        columns = ("id", "title", "type", "status", "ver", "updated", "owner", "active")
        self.tree = ttk.Treeview(left, columns=columns, show="headings", selectmode="browse")
        self.tree.grid(row=1, column=0, sticky="nsew")

        _h = self.tree.heading
        _c = self.tree.column
        _h("id", text="ID");            _c("id", width=150, stretch=False, anchor="w")
        _h("title", text=T("documents.col.title") or "Titel");  _c("title", width=300, anchor="w")
        _h("type", text=T("documents.col.type") or "Typ");      _c("type", width=80, anchor="center")
        _h("status", text=T("documents.col.status") or "Status"); _c("status", width=110, anchor="center")
        _h("ver", text=T("documents.col.version") or "Version");  _c("ver", width=80, anchor="center")
        _h("updated", text=T("documents.col.updated") or "Geändert"); _c("updated", width=150, anchor="center")
        _h("owner", text=T("documents.col.owner") or "Owner");  _c("owner", width=120, anchor="w")
        _h("active", text=T("documents.col.active") or "Aktiv"); _c("active", width=60, anchor="center")

        self.tree.bind("<<TreeviewSelect>>", lambda e: self._on_select())

        # Right: details
        right = ttk.Notebook(body)
        body.add(right, weight=2)

        self.tab_overview = ttk.Frame(right)
        right.add(self.tab_overview, text=T("documents.tab.overview") or "Übersicht")
        self._build_overview(self.tab_overview)

        self.tab_comments = ttk.Frame(right)
        right.add(self.tab_comments, text=T("documents.tab.comments") or "Kommentare")
        self._build_comments(self.tab_comments)

        # Footer actions
        footer = ttk.Frame(self)
        footer.grid(row=2 if not self._init_error else 3, column=0, sticky="ew", padx=12, pady=(0, 12))
        footer.columnconfigure(7, weight=1)

        self.btn_open = ttk.Button(footer, text=T("common.open") or "Öffnen", command=self._open_current)
        self.btn_copy = ttk.Button(footer, text=T("documents.btn.copy") or "Kopie erstellen", command=self._copy)
        self.btn_assign_roles = ttk.Button(footer, text=T("documents.btn.assign") or "Rollen zuweisen",
                                           command=lambda: self._assign_roles(force=True))
        self.btn_workflow = ttk.Button(footer, text=T("documents.btn.workflow.start") or "Workflow starten",
                                       command=self._toggle_workflow)
        self.btn_next = ttk.Button(footer, text=T("documents.btn.next") or "Nächster Schritt",
                                   command=self._next_step)
        self.btn_back_to_draft = ttk.Button(footer, text=T("documents.btn.back") or "Zurück zu Entwurf",
                                            command=self._back_to_draft)
        self.btn_archive = ttk.Button(footer, text=T("documents.btn.archive") or "Archivieren",
                                      command=self._archive)
        self.btn_refresh = ttk.Button(footer, text=T("common.reload") or "Aktualisieren",
                                      command=self._reload)

        self.btn_open.grid(row=0, column=0, padx=(0, 6))
        self.btn_copy.grid(row=0, column=1, padx=(0, 6))
        self.btn_assign_roles.grid(row=0, column=2, padx=(0, 6))
        self.btn_workflow.grid(row=0, column=3, padx=(0, 6))
        self.btn_next.grid(row=0, column=4, padx=(0, 6))
        self.btn_back_to_draft.grid(row=0, column=5, padx=(0, 6))
        self.btn_archive.grid(row=0, column=6, padx=(0, 6))
        self.btn_refresh.grid(row=0, column=7, sticky="e")

    # --------------------------------------------------------------- UI parts
    def _build_overview(self, parent: tk.Misc) -> None:
        """
        Build the overview tab.
        Changes in this version:
        - Metadata block is rendered vertically (label above value, stacked).
        """
        parent.columnconfigure(1, weight=1)

        r = 0
        ttk.Label(parent, text=T("documents.ov.id") or "Dokumenten-ID:", font=("Segoe UI", 10, "bold")).grid(row=r, column=0, sticky="w", padx=(8, 4), pady=(8, 2))
        self.l_id = ttk.Label(parent, text="—"); self.l_id.grid(row=r, column=1, sticky="w", padx=(0, 8), pady=(8, 2)); r += 1

        ttk.Label(parent, text=T("documents.ov.title") or "Titel:", font=("Segoe UI", 10, "bold")).grid(row=r, column=0, sticky="w", padx=(8, 4), pady=2)
        self.l_title = ttk.Label(parent, text="—"); self.l_title.grid(row=r, column=1, sticky="w", padx=(0, 8), pady=2); r += 1

        ttk.Label(parent, text=T("documents.ov.type") or "Typ:", font=("Segoe UI", 10, "bold")).grid(row=r, column=0, sticky="w", padx=(8, 4), pady=2)
        self.l_type = ttk.Label(parent, text="—"); self.l_type.grid(row=r, column=1, sticky="w", padx=(0, 8), pady=2); r += 1

        ttk.Label(parent, text=T("documents.ov.status") or "Status:", font=("Segoe UI", 10, "bold")).grid(row=r, column=0, sticky="w", padx=(8, 4), pady=2)
        self.l_status = ttk.Label(parent, text="—"); self.l_status.grid(row=r, column=1, sticky="w", padx=(0, 8), pady=2); r += 1

        ttk.Label(parent, text=T("documents.ov.version") or "Version:", font=("Segoe UI", 10, "bold")).grid(row=r, column=0, sticky="w", padx=(8, 4), pady=2)
        self.l_version = ttk.Label(parent, text="—"); self.l_version.grid(row=r, column=1, sticky="w", padx=(0, 8), pady=2); r += 1

        ttk.Label(parent, text=T("documents.ov.updated") or "Geändert:", font=("Segoe UI", 10, "bold")).grid(row=r, column=0, sticky="w", padx=(8, 4), pady=2)
        self.l_updated = ttk.Label(parent, text="—"); self.l_updated.grid(row=r, column=1, sticky="w", padx=(0, 8), pady=2); r += 1

        ttk.Label(parent, text=T("documents.ov.path") or "Aktuelle Datei:", font=("Segoe UI", 10, "bold")).grid(row=r, column=0, sticky="w", padx=(8, 4), pady=2)
        self.l_path = ttk.Label(parent, text="—", justify="left", wraplength=560)
        self.l_path.grid(row=r, column=1, sticky="w", padx=(0, 8), pady=2); r += 1

        ttk.Separator(parent).grid(row=r, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 6)); r += 1

        # Current actors (effective) – unchanged (grid header + one data row)
        ttk.Label(parent, text=T("documents.ov.actors") or "Aktuelle Bearbeiter", font=("Segoe UI", 10, "bold")).grid(row=r, column=0, sticky="w", padx=(8,4), pady=(2,2)); r += 1
        grid = ttk.Frame(parent); grid.grid(row=r, column=0, columnspan=2, sticky="ew", padx=6); r += 1
        for i in range(6):
            grid.columnconfigure(i, weight=1)

        ttk.Label(grid, text=T("documents.role.editor") or "Bearbeiter").grid(row=0, column=0, sticky="w")
        ttk.Label(grid, text=T("documents.role.reviewer") or "Prüfer").grid(row=0, column=1, sticky="w")
        ttk.Label(grid, text=T("documents.role.publisher") or "Freigeber").grid(row=0, column=2, sticky="w")
        ttk.Label(grid, text=T("documents.role.editor_dt") or "Bearb.-Datum").grid(row=0, column=3, sticky="w")
        ttk.Label(grid, text=T("documents.role.reviewer_dt") or "Prüf.-Datum").grid(row=0, column=4, sticky="w")
        ttk.Label(grid, text=T("documents.role.publisher_dt") or "Freig.-Datum").grid(row=0, column=5, sticky="w")

        self.l_exec_editor = ttk.Label(grid, text="—");        self.l_exec_editor.grid(row=1, column=0, sticky="w")
        self.l_exec_reviewer = ttk.Label(grid, text="—");      self.l_exec_reviewer.grid(row=1, column=1, sticky="w")
        self.l_exec_publisher = ttk.Label(grid, text="—");     self.l_exec_publisher.grid(row=1, column=2, sticky="w")
        self.l_dt_editor = ttk.Label(grid, text="—");          self.l_dt_editor.grid(row=1, column=3, sticky="w")
        self.l_dt_reviewer = ttk.Label(grid, text="—");        self.l_dt_reviewer.grid(row=1, column=4, sticky="w")
        self.l_dt_publisher = ttk.Label(grid, text="—");       self.l_dt_publisher.grid(row=1, column=5, sticky="w")

        ttk.Separator(parent).grid(row=r, column=0, columnspan=2, sticky="ew", padx=8, pady=(12, 6)); r += 1

        # -------------------- Metadata block (VERTICAL layout: label above value)
        meta = ttk.Frame(parent)
        meta.grid(row=r, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 8))
        meta.columnconfigure(0, weight=1)

        def _mkrow_vertical(label_text: str) -> ttk.Label:
            """
            Create a vertical field: bold label on first line, value on second line.
            Returns the ttk.Label that holds the value.
            """
            row = ttk.Frame(meta)
            row.grid(sticky="ew", pady=(2, 4))
            # Label (bold)
            ttk.Label(row, text=label_text + ":", font=("Segoe UI", 10, "bold")).pack(anchor="w")
            # Value (wrapped)
            val = ttk.Label(row, text="—", justify="left", wraplength=560)
            val.pack(anchor="w", padx=(12, 0))
            return val

        self._meta_map: Dict[str, ttk.Label] = {
            "l_desc": _mkrow_vertical(T("documents.meta.description") or "Beschreibung"),
            "l_dtype": _mkrow_vertical(T("documents.meta.type") or "Dokumententyp"),
            "l_actual_ftype": _mkrow_vertical(T("documents.meta.actual_filetype") or "Dateityp (aktuell)"),
            "l_valid": _mkrow_vertical(T("documents.meta.valid_by_date") or "Gültig bis"),
            "l_lastmod": _mkrow_vertical(T("documents.meta.last_modified") or "Zuletzt geändert"),
        }

    def _build_comments(self, parent: tk.Misc) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        ttk.Label(parent, text=T("documents.comments.title") or "Kommentare",
                  font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))

        cols = ("author", "date", "preview")
        self.tv_comments = ttk.Treeview(parent, columns=cols, show="headings", selectmode="browse")
        self.tv_comments.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.tv_comments.heading("author", text=T("documents.comments.author") or "Autor")
        self.tv_comments.heading("date", text=T("documents.comments.date") or "Datum")
        self.tv_comments.heading("preview", text=T("documents.comments.text") or "Text (Vorschau)")
        self.tv_comments.column("author", width=160, anchor="w")
        self.tv_comments.column("date", width=140, anchor="center")
        self.tv_comments.column("preview", width=520, anchor="w")
        self.tv_comments.bind("<Double-1>", self._open_comment_detail)

    # --------------------------------------------------------------- list ops
    def _status_from_combo(self) -> Optional[DocumentStatus]:
        m = {
            (T("documents.status.draft") or "Entwurf"): DocumentStatus.DRAFT,
            (T("documents.status.review") or "Prüfung"): DocumentStatus.IN_REVIEW,
            (T("documents.status.approval") or "Freigabe"): DocumentStatus.APPROVAL,
            (T("documents.status.published") or "Veröffentlicht"): DocumentStatus.PUBLISHED,
            (T("documents.status.obsolete") or "Obsolet"): DocumentStatus.OBSOLETE,
        }
        txt = (self.cb_status.get() or "").strip()
        return m.get(txt, None)

    def _apply_sort(self, items: List[DocumentRecord], sort_mode: str) -> List[DocumentRecord]:
        mode = (sort_mode or "").lower()
        if mode.startswith("status"):
            order = {
                DocumentStatus.DRAFT: 0,
                DocumentStatus.IN_REVIEW: 1,
                DocumentStatus.APPROVAL: 2,
                DocumentStatus.PUBLISHED: 3,
                DocumentStatus.OBSOLETE: 4,
            }
            return sorted(items, key=lambda r: order.get(r.status, 99))
        if mode.startswith("titel") or mode.startswith("title"):
            return sorted(items, key=lambda r: (r.title or "").lower())
        # default: updated desc
        return sorted(items, key=lambda r: (r.updated_at or ""), reverse=True)

    def _reload(self) -> None:
        """Reload the list according to filters."""
        if self._init_error:
            return
        if self._loading:
            return
        self._loading = True
        try:
            # Clear table
            try:
                for iid in self.tree.get_children():
                    self.tree.delete(iid)
            except Exception:
                pass
            self._rows.clear()

            # Fetch
            search = self.e_search.get().strip() or None
            status = self._status_from_combo()
            active_only = bool(self.var_active_only.get())
            sort_mode = (self.cb_sort.get() or "").strip()

            # IMPORTANT: controller signature is usually (text, status, active_only)
            try:
                rows: List[DocumentRecord] = self.ctrl.list_documents(search, status, active_only)
            except TypeError:
                # Fallback: some implementations may still use keywords or different order
                try:
                    rows = self.ctrl.list_documents(text=search, status=status, active_only=active_only)  # type: ignore
                except Exception:
                    rows = self.ctrl.list_documents(search, status)  # type: ignore

            # Local sort (controller/repo returns "updated desc" by default)
            rows = self._apply_sort(rows, sort_mode)

            # Fill
            for r in rows:
                iid = str(getattr(r.doc_id, "value", r.doc_id))
                if iid.startswith("<class"):
                    iid = str(r.doc_id.value if hasattr(r.doc_id, "value") else r.doc_id)
                ver = f"{getattr(r, 'version_major', 1)}.{getattr(r, 'version_minor', 0)}"
                updated = getattr(r, "updated_at", "") or ""
                owner = getattr(r, "created_by", "") or ""
                active = "✓" if r.status in (DocumentStatus.DRAFT, DocumentStatus.IN_REVIEW, DocumentStatus.APPROVAL) else ""
                self.tree.insert(
                    "", "end", iid=iid,
                    values=(iid, r.title or "", r.doc_type or "", r.status.name if hasattr(r.status, "name") else str(r.status),
                            ver, updated, owner, active)
                )
                self._rows[iid] = r
        finally:
            self._loading = False
        self._on_select()

    # --------------------------------------------------------------- selection
    def _selected_record(self) -> Optional[DocumentRecord]:
        sel = self.tree.selection()
        if not sel:
            return None
        iid = sel[0]
        rec = self._rows.get(iid)
        if rec:
            return rec
        try:
            return self.ctrl.get_document(iid)
        except Exception:
            return None

    def _on_select(self) -> None:
        if self._loading:
            return
        rec = self._selected_record()
        self._fill_overview(rec)
        self._fill_comments(rec)
        self._refresh_controls(rec)

    # --------------------------------------------------------------- details
    def _fill_overview(self, rec: Optional[DocumentRecord]) -> None:
        def _set(lbl: ttk.Label, val: Any) -> None:
            lbl.configure(text=str(val) if val not in (None, "") else "—")

        if not rec:
            _set(self.l_id, "—"); _set(self.l_title, "—"); _set(self.l_type, "—")
            _set(self.l_status, "—"); _set(self.l_version, "—"); _set(self.l_updated, "—")
            _set(self.l_path, "—")
            for k in self._meta_map.values():
                k.configure(text="—")
            for lbl in (self.l_exec_editor, self.l_exec_reviewer, self.l_exec_publisher,
                        self.l_dt_editor, self.l_dt_reviewer, self.l_dt_publisher):
                lbl.configure(text="—")
            return

        _set(self.l_id, getattr(rec.doc_id, "value", rec.doc_id))
        _set(self.l_title, rec.title or "")
        _set(self.l_type, rec.doc_type or "")
        _set(self.l_status, rec.status.name if hasattr(rec.status, "name") else str(rec.status))
        _set(self.l_version, f"{getattr(rec, 'version_major', 1)}.{getattr(rec, 'version_minor', 0)}")
        _set(self.l_updated, getattr(rec, "updated_at", "") or "")
        _set(self.l_path, getattr(rec, "current_file_path", "") or "")

        # Effective actors for current step
        try:
            exec_info: Dict[str, Any] = {}
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

        # Meta & docx-extracted info
        details: Dict[str, Any] = {}
        try:
            if hasattr(self.ctrl, "get_document_details"):
                details = self.ctrl.get_document_details(rec) or {}
        except Exception:
            details = {}

        self._meta_map["l_desc"].configure(text=details.get("description") or "—")
        self._meta_map["l_dtype"].configure(text=details.get("documenttype") or rec.doc_type or "—")
        path = rec.current_file_path or ""
        ftype = details.get("actual_filetype") or (os.path.splitext(path)[1][1:].upper() if path else "—")
        self._meta_map["l_actual_ftype"].configure(text=ftype)
        self._meta_map["l_valid"].configure(text=details.get("valid_by_date") or "—")
        self._meta_map["l_lastmod"].configure(text=details.get("last_modified") or getattr(rec, "updated_at", "") or "—")

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

        def preview(text: str, n: int = 40) -> str:
            text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
            return (text[:n] + ("…" if len(text) > n else "")).replace("\n", " ")

        for c in (comments or []):
            try:
                self.tv_comments.insert("", "end",
                                        values=(c.get("author"), c.get("date"), preview(c.get("text", ""))))
            except Exception:
                continue

    def _open_comment_detail(self, event=None) -> None:
        """Modal window with full comment text."""
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

        if repo and rec:
            try:
                for c in repo.list_comments(rec.doc_id.value):
                    if (c.get("author") == author) and (c.get("date") == date):
                        full_text = c.get("text") or ""
                        break
            except Exception:
                pass

        if not full_text and len(vals) > 2:
            full_text = str(vals[2])

        win = tk.Toplevel(self)
        win.title(T("documents.comments.detail") or "Kommentar")
        win.geometry("700x440")
        frm = ttk.Frame(win, padding=12); frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=f"Author: {author or '—'}").pack(anchor="w")
        ttk.Label(frm, text=f"Date:   {date or '—'}").pack(anchor="w")
        txt = tk.Text(frm, wrap="word", height=16)
        txt.pack(fill="both", expand=True, pady=(8, 0))
        txt.insert("1.0", full_text or "(kein Text)")
        txt.configure(state="disabled")
        ttk.Button(frm, text=T("common.close") or "Schließen", command=win.destroy).pack(anchor="e", pady=(8, 0))

    # --------------------------------------------------------------- actions
    def _refresh_controls(self, rec: Optional[DocumentRecord]) -> None:
        for btn in [self.btn_workflow, self.btn_next, self.btn_back_to_draft, self.btn_archive, self.btn_open, self.btn_copy]:
            btn.configure(state="disabled")
        self.btn_assign_roles.configure(state="disabled")

        if not rec:
            return

        state = self.ctrl.compute_controls_state(rec)

        self.btn_workflow.configure(text=state.workflow_text)
        self.btn_next.configure(text=state.next_text)

        self.btn_open.configure(state=("normal" if state.can_open else "disabled"))
        self.btn_copy.configure(state=("normal" if state.can_copy else "disabled"))
        # names aligned with controller state
        self.btn_assign_roles.configure(
            state=("normal" if state.can_assign_roles else "disabled")
        )
        self.btn_workflow.configure(
            state=("normal" if state.can_toggle_workflow else "disabled")
        )
        self.btn_next.configure(state=("normal" if state.can_next else "disabled"))
        self.btn_back_to_draft.configure(state=("normal" if state.can_back_to_draft else "disabled"))
        self.btn_archive.configure(state=("normal" if state.can_archive else "disabled"))

    def _toggle_workflow(self) -> None:
        rec = self._selected_record()
        if not rec:
            return

        st = self.ctrl.compute_controls_state(rec)
        if "abbrechen" in st.workflow_text.lower() or "abort" in st.workflow_text.lower():
            pwd = simpledialog.askstring(T("documents.ask.pwd.title") or "Passwort",
                                         T("documents.ask.pwd") or "Bitte Passwort eingeben:",
                                         parent=self, show="*")
            if not pwd:
                return
            reason = self._ask_reason(T("documents.reason.abort") or "Grund – Abbrechen")
            if reason is None:
                return
            ok, msg = self.ctrl.abort_workflow(rec, pwd, reason)
        else:
            ok = self.ctrl.start_workflow(rec, ensure_assignments=lambda: self._assign_roles(force=True))
            msg = None

        if not ok and msg:
            messagebox.showerror(T("documents.workflow.err") or "Workflow", msg, parent=self)
        self._reload()

    def _next_step(self) -> None:
        rec = self._selected_record()
        if not rec:
            return
        reason = self._ask_reason(self.btn_next.cget("text"))
        if reason is None:
            return
        ok, msg = self.ctrl.forward_transition(
            rec,
            ask_reason=lambda: reason,
            sign_pdf=self._interactive_sign,  # MUST accept (pdf_path, reason) and return signed path or None
        )
        if not ok and msg:
            messagebox.showerror(T("documents.next.err") or "Fehler", msg, parent=self)
        self._reload()

    def _back_to_draft(self) -> None:
        rec = self._selected_record()
        if not rec:
            return
        reason = self._ask_reason(T("documents.reason.back") or "Grund – Zurücksetzen")
        if reason is None:
            return
        ok, msg = self.ctrl.backward_to_draft(rec, reason)
        if not ok and msg:
            messagebox.showerror(T("documents.back.err") or "Fehler", msg, parent=self)
        self._reload()

    def _archive(self) -> None:
        rec = self._selected_record()
        if not rec:
            return
        reason = self._ask_reason(T("documents.reason.archive") or "Grund – Archivieren")
        if reason is None:
            return
        ok, msg = self.ctrl.archive(rec, ask_reason=lambda: reason)
        if not ok and msg:
            messagebox.showerror(T("documents.archive.err") or "Fehler", msg, parent=self)
        self._reload()

    # ----------------------------------------------------------- helper dialogs
    def _ask_reason(self, title: str) -> Optional[str]:
        s = simpledialog.askstring(T("documents.ask.reason.title") or "Begründung",
                                   (T("documents.ask.reason") or "Bitte eine kurze Begründung eingeben:")
                                   + f"\n({title})",
                                   parent=self)
        if s is None:
            return None
        s = s.strip()
        if not s:
            return None
        return s

    # MUST accept (pdf_path, reason) -> Optional[str]
    def _interactive_sign(self, pdf_path: str, reason: str) -> Optional[str]:
        """
        Let the Signatur-Modul place & sign. We only ensure sane defaults for settings
        to avoid Tk double-var cast errors if user-specific entries are missing.
        """
        try:
            self._ensure_signature_defaults()
        except Exception:
            pass

        try:
            # Support both styles: AppContext.signature() or AppContext.signature object
            sig_factory_or_obj = getattr(AppContext, "signature", None)
            if sig_factory_or_obj is None:
                messagebox.showerror("Signatur", "Signaturmodul nicht vorhanden.", parent=self)
                return None
            sig_api = sig_factory_or_obj() if callable(sig_factory_or_obj) else sig_factory_or_obj

            try:
                out = sig_api.place_and_sign(parent=self, pdf_path=pdf_path, reason=reason)
            except TypeError:
                out = sig_api.place_and_sign(self, pdf_path, reason)

            if isinstance(out, str) and os.path.isfile(out):
                return out
            if isinstance(out, dict):
                p = out.get("out") or out.get("path") or out.get("pdf")
                if isinstance(p, str) and os.path.isfile(p):
                    return p
            if hasattr(out, "path"):
                p = getattr(out, "path")
                if isinstance(p, str) and os.path.isfile(p):
                    return p
            return None
        except Exception as ex:
            messagebox.showerror("Signatur", str(ex), parent=self)
            return None

    def _ensure_signature_defaults(self) -> None:
        """
        Populate missing numeric/text signature settings so the signature dialog's preview
        does not try to cast "" to float. We do NOT modify the signature module itself.
        """
        user = getattr(AppContext, "current_user", None)
        uid = getattr(user, "id", None)

        namespaces = ["signature", "core_signature"]
        defaults: Dict[str, Any] = {
            "name_above": 2.0,
            "date_above": 2.0,
            "name": getattr(user, "display_name", None) or getattr(user, "name", "") or "",
            "date_fmt": "%d.%m.%Y",
            "reason_default": T("signature.default_reason") or "Genehmigt",
        }

        for ns in namespaces:
            def _get(k: str, d: Any) -> Any:
                if uid:
                    return self._sm.get(ns, k, d, user_specific=True, user_id=uid)
                return self._sm.get(ns, k, d)

            dirty: List[Tuple[str, Any]] = []
            for k, d in defaults.items():
                v = _get(k, d)
                if k in ("name_above", "date_above"):
                    try:
                        float(v)
                    except Exception:
                        dirty.append((k, d))
                else:
                    if v is None or v == "":
                        dirty.append((k, d))

            for k, v in dirty:
                if uid:
                    self._sm.set(ns, k, v, user_specific=True, user_id=uid)
                else:
                    self._sm.set(ns, k, v)

    # ----------------------------------------------------------- repo passthroughs
    def _open_current(self) -> None:
        rec = self._selected_record()
        if not rec:
            return
        try:
            path = getattr(rec, "current_file_path", None)
            if not path or not os.path.isfile(path):
                messagebox.showerror(title=(T("documents.open.error") or "Öffnen fehlgeschlagen"),
                                     message=T("documents.open.nofile") or "Datei nicht gefunden.",
                                     parent=self)
                return
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            elif os.name == "posix":
                import subprocess
                subprocess.Popen(["xdg-open", path])
            else:
                messagebox.showinfo("Open", path, parent=self)
        except Exception as ex:
            messagebox.showerror(title=(T("documents.open.error") or "Open failed"), message=str(ex), parent=self)

    def _import_file(self) -> None:
        repo = getattr(self.ctrl, "_repo", None)
        if not repo:
            return
        path = filedialog.askopenfilename(parent=self, title=(T("documents.import.title") or "Dokument importieren"),
                                          filetypes=[("DOCX", "*.docx"), ("All", "*.*")])
        if not path:
            return
        rec = repo.create_from_file(title=None, doc_type="SOP", user_id=self.ctrl.current_user_id(), src_file=path)
        messagebox.showinfo(title=(T("documents.import.ok") or "Importiert"),
                            message=(T("documents.import.msg") or "Dokument angelegt: ") + rec.doc_id.value, parent=self)
        self._reload()

    def _new_from_template(self) -> None:
        repo = getattr(self.ctrl, "_repo", None)
        if not repo:
            return
        proj_root = os.path.abspath(os.path.join(os.getcwd()))
        tdir = os.path.join(proj_root, "templates")
        if not os.path.isdir(tdir):
            messagebox.showwarning(title=(T("documents.tpl.missing.title") or "Keine Vorlagen"),
                                   message=(T("documents.tpl.missing.msg") or "Ordner nicht gefunden: ") + tdir, parent=self)
            return
        path = filedialog.askopenfilename(parent=self, title=(T("documents.tpl.choose") or "Vorlage wählen"),
                                          initialdir=tdir, filetypes=[("DOCX", "*.docx"), ("All", "*.*")])
        if not path:
            return
        rec = repo.create_from_file(title=None, doc_type="SOP", user_id=self.ctrl.current_user_id(), src_file=path)
        messagebox.showinfo(title=(T("documents.tpl.created") or "Dokument erstellt"),
                            message=(T("documents.tpl.created.msg") or "Erstellt aus Vorlage: ") + rec.doc_id.value,
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
            self._reload()
            self._on_select()

    def _copy(self) -> None:
        repo = getattr(self.ctrl, "_repo", None)
        if not repo:
            return
        rec = self._selected_record()
        if not rec or rec.status != DocumentStatus.PUBLISHED:
            return
        dest_dir = filedialog.askdirectory(parent=self, title=(T("documents.copy.choose_dest") or "Zielordner wählen"))
        if not dest_dir:
            return
        try:
            out = repo.copy_to_destination(rec.doc_id.value, dest_dir)
            if out:
                messagebox.showinfo(title=(T("documents.copy.ok") or "Kopie erstellt"),
                                    message=(T("documents.copy.done") or "Kopie erstellt in: ") + out, parent=self)
        except Exception as ex:
            messagebox.showerror("Copy", str(ex), parent=self)

    # --------------------------------------------------------------- roles
    def _assign_roles(self, force: bool = False) -> bool:
        """
        Open role assignment dialog if needed. Returns True if assignments exist and are valid.
        """
        rec = self._selected_record()
        if not rec:
            return False

        current = self.ctrl.get_assignees(rec.doc_id.value) or {}

        if force or not any(bool(current.get(k)) for k in ("authors", "reviewers", "approvers")):
            if AssignRolesDialog:
                dlg = AssignRolesDialog(self, current=current)  # type: ignore
                self.wait_window(dlg)
                result = getattr(dlg, "result", None)
                if not result:
                    return False
                a = Assignments(authors=result.get("authors"), reviewers=result.get("reviewers"), approvers=result.get("approvers"))
            else:
                authors = simpledialog.askstring("Rollen", "Bearbeiter (',' getrennt):", parent=self) or ""
                reviewers = simpledialog.askstring("Rollen", "Prüfer (',' getrennt):", parent=self) or ""
                approvers = simpledialog.askstring("Rollen", "Freigeber (',' getrennt):", parent=self) or ""
                a = Assignments(
                    authors=[s.strip() for s in authors.split(",") if s.strip()],
                    reviewers=[s.strip() for s in reviewers.split(",") if s.strip()],
                    approvers=[s.strip() for s in approvers.split(",") if s.strip()],
                )

            # Business rule: reviewer and approver must not be the same person
            try:
                ok, msg = self.ctrl.validate_assignments(a)
            except TypeError:
                ok, msg = self.ctrl.validate_assignments(a.reviewers or [], a.approvers or [])  # older signature
            if not ok:
                messagebox.showerror(T("documents.assign.err") or "Fehler", msg or "", parent=self)
                return False

            self.ctrl.set_assignees(rec.doc_id.value, a)

        return True
