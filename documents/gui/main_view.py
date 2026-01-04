"""
DocumentsView – main list/detail UI for the Documents feature.

REFACTORED VERSION with new architecture:
- Uses Service Layer (WorkflowPolicy, PermissionPolicy, UIStateService)
- Uses Repository with Adapters (DatabaseAdapter, StorageAdapter)
- Controllers are fully injected with dependencies
"""

from __future__ import annotations

import os
import logging
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from typing import Any, Dict, Optional, List
from pathlib import Path
from documents.services.policy.type_registry import TypeRegistry
from documents.services.ui_state_service import UIStateService

# Core services / i18n
from core.common.app_context import AppContext, T  # type: ignore
from core.settings.logic.settings_manager import SettingsManager  # type: ignore

# Models
from documents.models.document_models import DocumentRecord, DocumentStatus  # type: ignore

# Controllers (NEW ARCHITECTURE!)
from documents.controllers import (
    SearchFilterController,
    DocumentListController,
    DocumentDetailsController,
    DocumentCreationController,
    WorkflowController,
    AssignmentController,
)

# DTOs
from documents.dto.assignments import Assignments
from documents.dto.controls_state import ControlsState
from documents.dto.document_details import DocumentDetails

# Repository
from documents.repository.sqlite_document_repository import SQLiteDocumentRepository
from documents.repository.repo_config import RepoConfig


# Adapters
from documents.adapters.sqlite_adapter import SQLiteAdapter

# Services
from documents.services.policy.permission_policy import PermissionPolicy
from documents.services.policy.workflow_policy import WorkflowPolicy
from documents.services.policy.signature_policy import SignaturePolicy
from documents.services.ui_state_service import UIStateService

# Dialogs (optional – degrade gracefully if missing)
try:
    from documents.gui.dialogs.assign_roles_dialog import AssignRolesDialog  # type: ignore
except Exception:
    AssignRolesDialog = None  # type: ignore

try:
    from documents.gui.dialogs.metadata_dialog import MetadataDialog  # type: ignore
except Exception:
    MetadataDialog = None  # type: ignore

from pathlib import Path
logger = logging.getLogger(__name__)


class DocumentsView(ttk.Frame):
    """
    Main UI for Documents feature.

    NEW Architecture:
    - Renders UI only
    - Delegates all actions to controllers
    - Controllers use Services (Policy-driven)
    - Repository uses Adapters (DB/Storage-agnostic)
    """
    _FEATURE_ID = "documents"

    # ================================================================== INIT
    def __init__(self, parent:  tk.Misc, *, settings_manager: SettingsManager) -> None:
        super().__init__(parent)

        self._sm = settings_manager
        self._feature_dir = Path(__file__).resolve().parents[1]
        self._type_registry = TypeRegistry.load_from_directory(self._feature_dir)
        self._allowed_doc_types = tuple(sorted(self._type_registry.list_all().keys()))
        self._init_error:  Optional[str] = None
        self._loading:  bool = False  # Guard flag for reload
        # Document types: source of truth is documents_document_types.json
        self._feature_dir = Path(__file__).resolve().parents[1]
        self._type_registry = TypeRegistry.load_from_directory(self._feature_dir)
        self._allowed_doc_types = tuple(sorted(self._type_registry.list_all().keys()))

        # Initialize repository with adapters
        try:
            self._repo = self._init_repository()
            self._rbac = self._init_rbac()
        except Exception as ex:
            logger.exception("DocumentsView initialization failed")
            self._init_error = f"Repository initialization failed: {ex}"
            self._repo = None
            self._rbac = None

        # Initialize controllers with services (NEW!)
        self._init_controllers()

        # UI state
        self._rows: Dict[str, DocumentRecord] = {}
        self._current_sort_mode: str = "updated"

        # Build UI
        self._build_ui()
        self._reload()
        self._on_select()

    def _init_repository(self) -> SQLiteDocumentRepository:
        """Initialize documents repository with adapters."""
        base_dir = str(getattr(AppContext, "app_storage_dir", None) or os.getcwd())
        root_path = self._sm.get(self._FEATURE_ID, "repository_root", os.path.join(base_dir, "documents_repo"))
        db_path = os.path.join(root_path, "documents.db")
        allowed_doc_types = self._allowed_doc_types,

        cfg = RepoConfig(
            root_path=root_path,
            db_path=db_path,
            id_prefix=str(self._sm.get(self._FEATURE_ID, "id_prefix", "DOC")),
            id_pattern=str(self._sm.get(self._FEATURE_ID, "id_pattern", "{YYYY}-{seq:04d}")),
            review_months=int(self._sm.get(self._FEATURE_ID, "review_cycle_months", 24)),
            watermark_copy=str(self._sm.get(self._FEATURE_ID, "watermark_text", "KONTROLLKOPIE")),
            allowed_doc_types=self._allowed_doc_types,
        )


        # Create adapters (NEW!)
        db_adapter = SQLiteAdapter(db_path)

        # NOTE: StorageAdapter integration is not yet finalized. For now the repository
        # remains DB-only and file operations must be handled elsewhere.
        return SQLiteDocumentRepository(cfg, db_adapter=db_adapter)

    def _init_rbac(self) -> None:
        """Initialize optional RBAC service.

        The RBAC integration for the Documents module is currently optional. The
        AssignmentController can operate without an RBAC service (it will skip
        user discovery).
        """
        return None

    def _init_controllers(self) -> None:
        """Initialize all controllers with services."""
        if self._init_error or not self._repo:
            self.filter_ctrl = None
            self.list_ctrl = None
            self.details_ctrl = None
            self.creation_ctrl = None
            self.workflow_ctrl = None
            self.assignment_ctrl = None
            return

        user_provider = lambda: getattr(AppContext, "current_user", None)

        base_dir = Path(__file__).resolve().parents[1]

        self._permission_policy = PermissionPolicy.load_from_directory(base_dir)
        self._workflow_policy = WorkflowPolicy.load_from_directory(base_dir)

        ui_state_service = UIStateService(
            permission_policy=self._permission_policy,
            workflow_policy=self._workflow_policy
        )

        self.filter_ctrl = SearchFilterController(repository=self._repo)

        self.list_ctrl = DocumentListController(
            repository=self._repo,
            filter_controller=self.filter_ctrl
        )

        self.details_ctrl = DocumentDetailsController(
            repository=self._repo,
            ui_state_service=ui_state_service,
            current_user_provider=user_provider
        )

        self.creation_ctrl = DocumentCreationController(
            repository=self._repo,
            current_user_provider=user_provider
        )

        # WorkflowController - jetzt MIT sign_pdf_callback Support
        self.workflow_ctrl = WorkflowController(
            repository=self._repo,
            workflow_policy=self._workflow_policy,
            permission_policy=self._permission_policy,
            current_user_provider=user_provider
        )

        self.assignment_ctrl = AssignmentController(
            repository=self._repo,
            user_provider=self._get_all_system_users
        )
    def _get_all_system_users(self) -> List[Dict[str, str]]:
        """Get all users from UserManager."""
        try:
            from usermanagement.logic.user_manager import UserManager
            um = UserManager()
            all_users = um.get_all_users()

            return [
                {
                    "id": str(getattr(u, "id", "") or ""),
                    "username": str(getattr(u, "username", "") or ""),
                    "email": str(getattr(u, "email", "") or ""),
                    "full_name": str(getattr(u, "full_name", "") or ""),
                }
                for u in all_users
                if getattr(u, "username", None)
            ]
        except Exception as ex:
            logger.debug(f"Failed to get users: {ex}")
            return []
    def _get_all_system_users(self) -> List[Dict[str, str]]:
        """Get all users from UserManager for role assignment."""
        users = []

        try:
            # Try to get UserManager from AppContext
            user_manager = getattr(AppContext, "user_manager", None)

            if user_manager and hasattr(user_manager, "get_all_users"):
                all_users = user_manager.get_all_users()
                for u in all_users:
                    user_dict = {
                        "id": str(getattr(u, "id", "") or getattr(u, "user_id", "") or ""),
                        "username": str(getattr(u, "username", "") or ""),
                        "email": str(getattr(u, "email", "") or ""),
                        "full_name": str(getattr(u, "full_name", "") or getattr(u, "display_name", "") or ""),
                    }
                    if user_dict["username"]:
                        users.append(user_dict)

            # If no users found via user_manager, try direct import
            if not users:
                try:
                    from usermanagement.logic.user_manager import UserManager
                    um = UserManager()
                    all_users = um.get_all_users()
                    for u in all_users:
                        user_dict = {
                            "id": str(getattr(u, "id", "") or ""),
                            "username": str(getattr(u, "username", "") or ""),
                            "email": str(getattr(u, "email", "") or ""),
                            "full_name": str(getattr(u, "full_name", "") or ""),
                        }
                        if user_dict["username"]:
                            users.append(user_dict)
                except Exception as ex:
                    logger.debug(f"Direct UserManager import failed: {ex}")

        except Exception as ex:
            logger.debug(f"Failed to get users from UserManager: {ex}")

        # Fallback: at least include current user
        if not users:
            current = getattr(AppContext, "current_user", None)
            if current:
                user_dict = {
                    "id": str(getattr(current, "id", "") or ""),
                    "username": str(getattr(current, "username", "") or ""),
                    "email": str(getattr(current, "email", "") or ""),
                    "full_name": str(getattr(current, "full_name", "") or ""),
                }
                if user_dict["username"]:
                    users.append(user_dict)

        return users
    def _get_available_users_fallback(self) -> List[Dict[str, str]]:
        """Fallback method to get available users from various sources."""
        users = []

        # Try to get from AppContext
        try:
            # Check for user manager/service
            user_mgr = getattr(AppContext, "user_manager", None) or getattr(AppContext, "users", None)
            if user_mgr:
                if callable(user_mgr):
                    result = user_mgr()
                elif hasattr(user_mgr, "list_users"):
                    result = user_mgr.list_users()
                elif hasattr(user_mgr, "get_all"):
                    result = user_mgr.get_all()
                elif isinstance(user_mgr, (list, tuple)):
                    result = user_mgr
                else:
                    result = None

                if result:
                    for u in result:
                        users.append(self._extract_user_info(u))
        except Exception:
            pass

        # At minimum, include current user
        try:
            current = getattr(AppContext, "current_user", None)
            if current:
                user_info = self._extract_user_info(current)
                if user_info.get("id") or user_info.get("username"):
                    # Check if already in list
                    existing_ids = {u.get("id") for u in users}
                    if user_info.get("id") not in existing_ids:
                        users.append(user_info)
        except Exception:
            pass

        return users

    def _extract_user_info(self, user) -> Dict[str, str]:
        """Extract user info from various user object formats."""
        if isinstance(user, dict):
            return {
                "id": str(user.get("id", "") or user.get("user_id", "") or ""),
                "username": str(user.get("username", "") or user.get("name", "") or ""),
                "email": str(user.get("email", "") or ""),
                "full_name": str(user.get("full_name", "") or user.get("display_name", "") or ""),
            }

        return {
            "id": str(getattr(user, "id", "") or getattr(user, "user_id", "") or ""),
            "username": str(getattr(user, "username", "") or getattr(user, "name", "") or ""),
            "email": str(getattr(user, "email", "") or ""),
            "full_name": str(getattr(user, "full_name", "") or getattr(user, "display_name", "") or ""),
        }
    # ================================================================== UI BUILD
    def _build_ui(self) -> None:
        """Build complete UI structure."""
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Error banner (if init failed)
        if self._init_error:
            ttk.Label(
                self,
                text=(T("documents.init_error") or "Problem bei der Modulinitialisierung:  ") + str(self._init_error),
                foreground="#b00020",
                wraplength=780,
                justify="left",
            ).grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))

        # Header with search/filter
        header = ttk.Frame(self)
        header.grid(row=0 if not self._init_error else 1, column=0, sticky="ew", padx=12, pady=(12, 6))
        header.columnconfigure(10, weight=1)

        ttk.Label(header, text=(T("documents.title") or "Dokumentenlenkung"),
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
                T("documents.status.approved") or "Freigegeben",
                T("documents.status.effective") or "Gültig",
                T("documents.status.revision") or "Revision",
                T("documents.status.obsolete") or "Obsolet",
                T("documents.status.archived") or "Archiviert",
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

        # Split panel (list | details)
        body = ttk.Panedwindow(self, orient="horizontal")
        body.grid(row=1 if not self._init_error else 2, column=0, sticky="nsew", padx=12, pady=(4, 12))

        # Left:  list
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
        ttk.Button(listbar, text=T("documents.btn.edit_meta") or "Metadaten", command=self._edit_metadata)\
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

        # Right: details (notebook with tabs)
        right = ttk.Notebook(body)
        body.add(right, weight=2)

        self.tab_overview = ttk.Frame(right)
        right.add(self.tab_overview, text=T("documents.tab.overview") or "Übersicht")
        self._build_overview_tab(self.tab_overview)

        self.tab_comments = ttk.Frame(right)
        right.add(self.tab_comments, text=T("documents.tab.comments") or "Kommentare")
        self._build_comments_tab(self.tab_comments)

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

    def _build_overview_tab(self, parent: tk.Misc) -> None:
        """Build overview tab (details display)."""
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

        # Current actors
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

        # Metadata (vertical layout)
        meta = ttk.Frame(parent)
        meta.grid(row=r, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 8))
        meta.columnconfigure(0, weight=1)

        def _mkrow_vertical(label_text: str) -> ttk.Label:
            row = ttk.Frame(meta)
            row.grid(sticky="ew", pady=(2, 4))
            ttk.Label(row, text=label_text + ":", font=("Segoe UI", 10, "bold")).pack(anchor="w")
            val = ttk.Label(row, text="—", justify="left", wraplength=560)
            val.pack(anchor="w", padx=(12, 0))
            return val

        self._meta_map:  Dict[str, ttk.Label] = {
            "l_desc": _mkrow_vertical(T("documents.meta.description") or "Beschreibung"),
            "l_dtype": _mkrow_vertical(T("documents.meta.type") or "Dokumententyp"),
            "l_actual_ftype": _mkrow_vertical(T("documents.meta.actual_filetype") or "Dateityp (aktuell)"),
            "l_valid":  _mkrow_vertical(T("documents.meta.valid_by_date") or "Gültig bis"),
            "l_lastmod": _mkrow_vertical(T("documents.meta.last_modified") or "Zuletzt geändert"),
        }

    def _build_comments_tab(self, parent: tk.Misc) -> None:
        """Build comments tab."""
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

    # ================================================================== LIST OPERATIONS
    def _status_from_combo(self) -> Optional[DocumentStatus]:
        """Extract DocumentStatus from combo selection."""
        m = {
            (T("documents.status.draft") or "Entwurf"): DocumentStatus.DRAFT,
            (T("documents.status.review") or "Prüfung"): DocumentStatus.REVIEW,
            (T("documents.status.approved") or "Freigegeben"): DocumentStatus.APPROVED,
            (T("documents.status.effective") or "Gültig"): DocumentStatus.EFFECTIVE,
            (T("documents.status.revision") or "Revision"): DocumentStatus.REVISION,
            (T("documents.status.obsolete") or "Obsolet"): DocumentStatus.OBSOLETE,
            (T("documents.status.archived") or "Archiviert"): DocumentStatus.ARCHIVED,
        }
        txt = (self.cb_status.get() or "").strip()
        return m.get(txt, None)

    def _reload(self) -> None:
        """Reload list via DocumentListController."""
        if self._init_error or not self.list_ctrl:
            return
        if self._loading:
            return

        self._loading = True
        try:
            # Clear table
            for iid in self.tree.get_children():
                self.tree.delete(iid)
            self._rows.clear()

            # Collect filters
            search = self.e_search.get().strip() or None
            status = self._status_from_combo()
            active_only = bool(self.var_active_only.get())
            sort_mode_text = (self.cb_sort.get() or "").strip()

            # Map to sort mode
            if sort_mode_text.startswith("Status"):
                sort_mode = "status"
            elif sort_mode_text.startswith("Titel"):
                sort_mode = "title"
            else:
                sort_mode = "updated"

            self._current_sort_mode = sort_mode

            # Load via controller
            documents = self.list_ctrl.load_documents(
                text=search,
                status=status,
                active_only=active_only,
                sort_mode=sort_mode
            )

            # Fill tree
            for rec in documents:
                iid = str(rec.doc_id.value if hasattr(rec.doc_id, "value") else rec.doc_id)
                ver = f"{rec.version_major}.{rec.version_minor}"
                updated = str(rec.updated_at) if rec.updated_at else ""
                owner = str(rec.created_by) if rec.created_by else ""
                active = "✓" if rec.status in (
                    DocumentStatus.DRAFT,
                    DocumentStatus.REVIEW,
                    DocumentStatus.APPROVED,
                    DocumentStatus.EFFECTIVE,
                    DocumentStatus.REVISION,
                ) else ""

                self.tree.insert(
                    "", "end", iid=iid,
                    values=(
                        iid,
                        rec.title or "",
                        rec.doc_type or "",
                        rec.status.name if hasattr(rec.status, "name") else str(rec.status),
                        ver,
                        updated,
                        owner,
                        active
                    )
                )
                self._rows[iid] = rec
        finally:
            self._loading = False

        self._on_select()

    # ================================================================== SELECTION
    def _selected_record(self) -> Optional[DocumentRecord]:
        """Get currently selected document record."""
        sel = self.tree.selection()
        if not sel:
            return None
        iid = sel[0]
        rec = self._rows.get(iid)
        if rec:
            return rec

        # Fallback:  load from controller
        if self.list_ctrl:
            return self.list_ctrl.get_document(iid)
        return None

    def _on_select(self) -> None:
        """Handle selection change."""
        if self._loading:
            return

        rec = self._selected_record()
        self._fill_overview(rec)
        self._fill_comments(rec)
        self._refresh_controls(rec)

    # ================================================================== DETAILS RENDERING
    def _fill_overview(self, rec: Optional[DocumentRecord]) -> None:
        """Fill overview tab with details from DocumentDetailsController."""
        def _set(lbl: ttk.Label, val: Any) -> None:
            lbl.configure(text=str(val) if val not in (None, "") else "—")

        if not rec:
            # Clear all
            _set(self.l_id, "—"); _set(self.l_title, "—"); _set(self.l_type, "—")
            _set(self.l_status, "—"); _set(self.l_version, "—"); _set(self.l_updated, "—")
            _set(self.l_path, "—")
            for lbl in self._meta_map.values():
                lbl.configure(text="—")
            for lbl in (self.l_exec_editor, self.l_exec_reviewer, self.l_exec_publisher,
                        self.l_dt_editor, self.l_dt_reviewer, self.l_dt_publisher):
                lbl.configure(text="—")
            return

        # Get details via controller
        if not self.details_ctrl:
            return

        details:  Optional[DocumentDetails] = self.details_ctrl.get_details(rec.doc_id.value)
        if not details:
            return

        # Basic fields
        _set(self.l_id, details.doc_id)
        _set(self.l_title, details.title)
        _set(self.l_type, details.doc_type)
        _set(self.l_status, details.status)
        _set(self.l_version, details.version_label)
        _set(self.l_updated, str(rec.updated_at) if rec.updated_at else "")
        _set(self.l_path, details.current_file_path)

        # Actors
        _set(self.l_exec_editor, details.editor)
        _set(self.l_exec_reviewer, details.reviewer)
        _set(self.l_exec_publisher, details.publisher)
        _set(self.l_dt_editor, details.editor_dt)
        _set(self.l_dt_reviewer, details.reviewer_dt)
        _set(self.l_dt_publisher, details.publisher_dt)

        # Metadata
        self._meta_map["l_desc"].configure(text=details.description or "—")
        self._meta_map["l_dtype"].configure(text=details.documenttype or "—")
        self._meta_map["l_actual_ftype"].configure(text=details.actual_filetype or "—")
        self._meta_map["l_valid"].configure(text=details.valid_by_date or "—")
        self._meta_map["l_lastmod"].configure(text=details.last_modified or "—")

    def _fill_comments(self, rec: Optional[DocumentRecord]) -> None:
        """Fill comments tab."""
        # Clear tree
        for i in self.tv_comments.get_children():
            self.tv_comments.delete(i)

        if not rec or not self.details_ctrl:
            return

        # Get comments via controller
        comments = self.details_ctrl.get_comments(rec.doc_id.value)

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
        """Show full comment in modal window."""
        if self._loading:
            return

        sel = self.tv_comments.selection()
        if not sel:
            return

        item = self.tv_comments.item(sel[0])
        vals = item.get("values") or []
        author = vals[0] if len(vals) > 0 else ""
        date = vals[1] if len(vals) > 1 else ""

        # Get full text
        rec = self._selected_record()
        if not rec or not self.details_ctrl:
            return

        full_text = ""
        comments = self.details_ctrl.get_comments(rec.doc_id.value)
        for c in comments:
            if (c.get("author") == author) and (c.get("date") == date):
                full_text = c.get("text") or ""
                break

        # Show modal
        win = tk.Toplevel(self)
        win.title(T("documents.comments.detail") or "Kommentar")
        win.geometry("700x440")
        frm = ttk.Frame(win, padding=12); frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=f"Author: {author or '—'}").pack(anchor="w")
        ttk.Label(frm, text=f"Date:    {date or '—'}").pack(anchor="w")
        txt = tk.Text(frm, wrap="word", height=16)
        txt.pack(fill="both", expand=True, pady=(8, 0))
        txt.insert("1.0", full_text or "(kein Text)")
        txt.configure(state="disabled")
        ttk.Button(frm, text=T("common.close") or "Schließen", command=win.destroy).pack(anchor="e", pady=(8, 0))

    # ================================================================== CONTROLS STATE
    def _refresh_controls(self, rec: Optional[DocumentRecord]) -> None:
        """Update button states via DocumentDetailsController (NEW ARCHITECTURE!)."""
        # Default:  all disabled
        for btn in [self.btn_workflow, self.btn_next, self.btn_back_to_draft, self.btn_archive, self.btn_open, self.btn_copy]:
            btn.configure(state="disabled")
        self.btn_assign_roles.configure(state="disabled")

        if not rec or not self.details_ctrl:
            self.btn_workflow.configure(text="Workflow")
            self.btn_next.configure(text="Nächster Schritt")
            return

        # Get user roles (NEW:  using PermissionPolicy)
        user = getattr(AppContext, "current_user", None)
        user_roles = self._get_user_roles(user)
        assigned_roles = self._get_assigned_roles(rec.doc_id.value, user)

        # Compute state via controller (NEW!)
        state:  ControlsState = self.details_ctrl.compute_controls_state(
            rec,
            user_roles=user_roles,
            assigned_roles=assigned_roles
        )

        # Apply state
        self.btn_workflow.configure(text=state.workflow_text)
        self.btn_next.configure(text=state.next_text)

        self.btn_open.configure(state=("normal" if state.can_open else "disabled"))
        self.btn_copy.configure(state=("normal" if state.can_copy else "disabled"))
        self.btn_assign_roles.configure(state=("normal" if state.can_assign_roles else "disabled"))
        self.btn_workflow.configure(state=("normal" if state.can_toggle_workflow else "disabled"))
        self.btn_next.configure(state=("normal" if state.can_next else "disabled"))
        self.btn_back_to_draft.configure(state=("normal" if state.can_back_to_draft else "disabled"))
        self.btn_archive.configure(state=("normal" if state.can_archive else "disabled"))

    def _get_user_roles(self, user: object) -> list[str]:
        """
        Get user's system roles.

        Returns system roles (ADMIN, QMB, USER) which will be
        expanded to module roles by PermissionPolicy.
        """
        if not user:
            return []

        roles = []

        # Get role from user object
        if hasattr(user, 'role'):
            role = getattr(user, 'role', None)
            if role:
                # Handle enum or string
                role_name = str(role.name if hasattr(role, 'name') else role).upper()
                roles.append(role_name)

        # Also check roles list (if present)
        if hasattr(user, 'roles'):
            user_roles = getattr(user, 'roles', [])
            if isinstance(user_roles, (list, set)):
                for r in user_roles:
                    role_name = str(r.name if hasattr(r, 'name') else r).upper()
                    if role_name not in roles:
                        roles.append(role_name)

        # Fallback to USER if no roles
        if not roles:
            roles = ["USER"]

        return roles

    def _refresh_controls(self, rec: Optional[DocumentRecord]) -> None:
        """Update button states via UIStateService."""
        # Default:  all disabled
        for btn in [self.btn_workflow, self.btn_next, self.btn_back_to_draft,
                    self.btn_archive, self.btn_open, self.btn_copy]:
            btn.configure(state="disabled")
        self.btn_assign_roles.configure(state="disabled")

        if not rec or not self.details_ctrl:
            self.btn_workflow.configure(text="Workflow")
            self.btn_next.configure(text="Nächster Schritt")
            return

        # Get user info
        user = getattr(AppContext, "current_user", None)
        user_roles = self._get_user_roles(user)
        assigned_roles = self._get_assigned_roles(rec.doc_id.value, user)

        # Get user_id for ownership check
        user_id = None
        if user:
            for attr in ("id", "user_id", "username"):
                val = getattr(user, attr, None)
                if val:
                    user_id = str(val)
                    break

        # Compute state via controller
        state: ControlsState = self.details_ctrl.compute_controls_state(
            rec,
            user_roles=user_roles,
            assigned_roles=assigned_roles
        )

        # Apply state
        self.btn_workflow.configure(text=state.workflow_text)
        self.btn_next.configure(text=state.next_text)

        self.btn_open.configure(state=("normal" if state.can_open else "disabled"))
        self.btn_copy.configure(state=("normal" if state.can_copy else "disabled"))
        self.btn_assign_roles.configure(state=("normal" if state.can_assign_roles else "disabled"))
        self.btn_workflow.configure(state=("normal" if state.can_toggle_workflow else "disabled"))
        self.btn_next.configure(state=("normal" if state.can_next else "disabled"))
        self.btn_back_to_draft.configure(state=("normal" if state.can_back_to_draft else "disabled"))
        self.btn_archive.configure(state=("normal" if state.can_archive else "disabled"))

    def _get_assigned_roles(self, doc_id: str, user: object) -> list[str]:
        """Get user's assigned roles on this document.

        The repository may store assignments by user_id (preferred) but the UI may
        have different user object shapes (id, user_id, username, email, ...).
        We therefore match against all available identifiers.
        """
        if not user or not self._repo:
            return []

        identifiers = self._get_user_identifiers(user)
        if not identifiers:
            return []

        assignees = self._repo.get_assignees(doc_id)
        assigned: list[str] = []

        # Expected shape in current repo: dict[str(role), list[str(user_id)]]
        if isinstance(assignees, dict):
            for role, users in assignees.items():
                if not users:
                    continue
                users_norm = {str(u).strip().lower() for u in users if u is not None}
                if identifiers & users_norm:
                    assigned.append(role)
            return assigned

        # Defensive fallback: list of dict rows (if repo implementation changes)
        if isinstance(assignees, list):
            for row in assignees:
                if not isinstance(row, dict):
                    continue
                role = row.get("role")
                uid = row.get("user_id") or row.get("username")
                if role and uid and str(uid).strip().lower() in identifiers:
                    assigned.append(str(role))
            return assigned

        return []

    def _get_user_id_from_object(self, user: object) -> Optional[str]:
        """Backwards compatible: return one stable identifier if present."""
        identifiers = self._get_user_identifiers(user)
        return next(iter(identifiers), None)

    def _get_user_identifiers(self, user: object) -> set[str]:
        """Return a set of normalized identifiers for the given user object."""
        identifiers: set[str] = set()

        def _add(val: object) -> None:
            if val is None:
                return
            s = str(val).strip()
            if s:
                identifiers.add(s.lower())

        if isinstance(user, dict):
            for key in ("id", "user_id", "uid", "username", "email", "name"):
                _add(user.get(key))
        else:
            for attr in ("id", "user_id", "uid", "username", "email", "name"):
                _add(getattr(user, attr, None))

        return identifiers

    # ================================================================== ACTIONS
    def _toggle_workflow(self) -> None:
        """Toggle workflow (start or abort)."""
        rec = self._selected_record()
        if not rec or not self.workflow_ctrl:
            return

        state = self.details_ctrl.compute_controls_state(
            rec,
            user_roles=self._get_user_roles(getattr(AppContext, "current_user", None)),
            assigned_roles=self._get_assigned_roles(rec.doc_id.value, getattr(AppContext, "current_user", None))
        )
        is_abort = "abbrechen" in state.workflow_text.lower() or "abort" in state.workflow_text.lower()

        if is_abort:
            pwd = simpledialog.askstring(
                T("documents.ask.pwd.title") or "Passwort",
                T("documents.ask.pwd") or "Bitte Passwort eingeben:",
                parent=self,
                show="*"
            )
            if not pwd:
                return

            reason = self._ask_reason(T("documents.reason.abort") or "Grund – Abbrechen")
            if reason is None:
                return

            user_roles = self._get_user_roles(getattr(AppContext, "current_user", None))

            # IMPORTANT: abort_workflow has keyword-only args after `reason`
            success, error_msg = self.workflow_ctrl.abort_workflow(
                rec.doc_id.value,
                reason=reason,
                password=pwd,
                user_roles=user_roles,
            )
        else:
            user_roles = self._get_user_roles(getattr(AppContext, "current_user", None))
            success, error_msg = self.workflow_ctrl.start_workflow(
                rec.doc_id.value,
                user_roles=user_roles,
                ensure_assignments_callback=lambda: self._assign_roles(force=True)
            )

        if not success:
            messagebox.showerror(
                T("documents.workflow.err") or "Workflow",
                error_msg or "Fehler",
                parent=self
            )

        self._reload()

    def _next_step(self) -> None:
        """Execute next workflow step."""
        rec = self._selected_record()
        if not rec or not self.workflow_ctrl:
            return

        reason = self._ask_reason(self.btn_next.cget("text"))
        if reason is None:
            return

        user = getattr(AppContext, "current_user", None)
        user_roles = self._get_user_roles(user)
        assigned_roles = self._get_assigned_roles(rec.doc_id.value, user)

        success, error_msg = self.workflow_ctrl.forward_transition(
            rec.doc_id.value,
            reason,
            user_roles=user_roles,
            assigned_roles=assigned_roles,
            sign_pdf_callback=self._interactive_sign
        )

        if not success:
            messagebox.showerror(T("documents.next.err") or "Fehler", error_msg or "Fehler", parent=self)

        self._reload()

    def _back_to_draft(self) -> None:
        """Revert to DRAFT."""
        rec = self._selected_record()
        if not rec or not self.workflow_ctrl:
            return

        reason = self._ask_reason(T("documents.reason.back") or "Grund – Zurücksetzen")
        if reason is None:
            return

        user_roles = self._get_user_roles(getattr(AppContext, "current_user", None))
        success, error_msg = self.workflow_ctrl.backward_to_draft(
            rec. doc_id.value, reason, user_roles=user_roles
        )

        if not success:
            messagebox.showerror(T("documents.back.err") or "Fehler", error_msg or "Fehler", parent=self)

        self._reload()

    def _archive(self) -> None:
        """Archive / obsolete document via forward transition.

        NOTE:
        - WorkflowController has no `archive()` method (would raise AttributeError).
        - We use forward_transition() so WorkflowPolicy decides whether action is
          'obsolete' (EFFECTIVE -> OBSOLETE) or 'archive' (OBSOLETE -> ARCHIVED).
        """
        rec = self._selected_record()
        if not rec or not self.workflow_ctrl:
            return

        reason = self._ask_reason(T("documents.reason.archive") or "Grund – Archivieren")
        if reason is None:
            return

        user = getattr(AppContext, "current_user", None)
        user_roles = self._get_user_roles(user)
        assigned_roles = self._get_assigned_roles(rec.doc_id.value, user)

        success, error_msg = self.workflow_ctrl.forward_transition(
            rec.doc_id.value,
            reason,
            user_roles=user_roles,
            assigned_roles=assigned_roles,
            sign_pdf_callback=None
        )

        if not success:
            messagebox.showerror(
                T("documents.archive.err") or "Archivieren",
                error_msg or "Fehler",
                parent=self
            )

        self._reload()

    # ================================================================== CREATION
    def _new_from_template(self) -> None:
        """Create document from template (DOTX/DOCX).

        Uses the existing MetadataDialog to select metadata (especially doc_type)
        BEFORE creation, so DB CHECK constraints are satisfied.
        """
        if not self.creation_ctrl:
            return

        proj_root = os.path.abspath(os.getcwd())
        tdir = os.path.join(proj_root, "templates")

        if not os.path.isdir(tdir):
            messagebox.showwarning(
                title=(T("documents.tpl.missing.title") or "Keine Vorlagen"),
                message=(T("documents.tpl.missing.msg") or "Ordner nicht gefunden: ") + tdir,
                parent=self
            )
            return

        path = filedialog.askopenfilename(
            parent=self,
            title=(T("documents.tpl.choose") or "Vorlage wählen"),
            initialdir=tdir,
            filetypes=[
                ("Word Vorlage", "*.dotx"),
                ("Word Dokument", "*.docx"),
                ("All", "*.*")
            ]
        )
        if not path:
            return

        # Allowed doc types come from registry (documents_document_types.json)
        allowed = list(getattr(self, "_allowed_doc_types", ()) or ())
        if not allowed:
            messagebox.showerror(
                "Fehler",
                "Keine erlaubten Dokumenttypen gefunden (TypeRegistry leer).",
                parent=self,
            )
            return

        # Use the existing MetadataDialog (same approach as import)
        class _TmpRecord:
            def __init__(self, title: str, doc_type: str) -> None:
                self.title = title
                self.doc_type = doc_type
                self.area = ""
                self.process = ""
                self.next_review = ""

        default_title = os.path.splitext(os.path.basename(path))[0]
        tmp = _TmpRecord(title=default_title, doc_type=allowed[0])

        dlg = MetadataDialog(self, tmp, allowed_types=allowed)
        self.wait_window(dlg)
        result = getattr(dlg, "result", None)
        if not result:
            return  # cancelled

        title = (getattr(result, "title", "") or "").strip() or default_title
        doc_type = (getattr(result, "doc_type", "") or "").strip()

        if doc_type not in allowed:
            messagebox.showerror(
                "Fehler",
                f"Ungültiger Dokumenttyp '{doc_type}'.\nErlaubt: {', '.join(allowed)}",
                parent=self,
            )
            return

        success, error_msg, record = self.creation_ctrl.create_from_template(path, doc_type=doc_type)
        if not success:
            messagebox.showerror("Fehler", error_msg or "Fehler beim Erstellen", parent=self)
            return

        # Optional: apply additional metadata post-create (if supported)
        try:
            if record and hasattr(self, "details_ctrl") and self.details_ctrl:
                meta = {
                    "title": title,
                    "doc_type": doc_type,
                    "area": getattr(result, "area", ""),
                    "process": getattr(result, "process", ""),
                    "next_review": getattr(result, "next_review", ""),
                }
                self.details_ctrl.update_metadata(getattr(record, "doc_id", ""), meta)
        except Exception:
            pass

        messagebox.showinfo(
            title=(T("documents.tpl.created") or "Dokument erstellt"),
            message=(T("documents.tpl.created.msg") or "Erstellt aus Vorlage: ") + (
                record.doc_id.value if record else ""),
            parent=self
        )
        self._reload()

    def _import_file(self) -> None:
        """Import DOCX file.

        Uses the existing MetadataDialog to select metadata (especially doc_type)
        BEFORE importing, so DB CHECK constraints are satisfied.
        """
        if not self.creation_ctrl:
            return

        path = filedialog.askopenfilename(
            parent=self,
            title="Dokument importieren",
            filetypes=[("DOCX", "*.docx"), ("All", "*.*")]
        )
        if not path:
            return

        # Allowed doc types come from registry (documents_document_types.json)
        allowed = list(getattr(self, "_allowed_doc_types", ()) or ())
        if not allowed:
            messagebox.showerror(
                "Import",
                "Keine erlaubten Dokumenttypen gefunden (TypeRegistry leer).",
                parent=self,
            )
            return

        # Create a lightweight "record-like" object for the dialog.
        # MetadataDialog only needs a few attributes; we don't need a DB record here.
        class _TmpRecord:
            def __init__(self, title: str, doc_type: str) -> None:
                self.title = title
                self.doc_type = doc_type
                self.area = ""
                self.process = ""
                self.next_review = ""

        default_title = os.path.splitext(os.path.basename(path))[0]
        tmp = _TmpRecord(title=default_title, doc_type=allowed[0])

        dlg = MetadataDialog(self, tmp, allowed_types=allowed)
        self.wait_window(dlg)
        result = getattr(dlg, "result", None)
        if not result:
            return  # cancelled

        # Collect metadata from dialog
        title = (getattr(result, "title", "") or "").strip() or default_title
        doc_type = (getattr(result, "doc_type", "") or "").strip()

        if doc_type not in allowed:
            messagebox.showerror(
                "Import",
                f"Ungültiger Dokumenttyp '{doc_type}'.\nErlaubt: {', '.join(allowed)}",
                parent=self,
            )
            return

        # Perform import with selected doc_type
        success, error_msg, record = self.creation_ctrl.import_file(path, doc_type=doc_type)

        if not success:
            messagebox.showerror("Import", error_msg or "Import fehlgeschlagen.", parent=self)
            return

        # Optional: apply additional metadata post-import, if your controller supports it.
        # (Only if update_metadata exists and you want title/area/process/next_review from dialog.)
        try:
            if record and hasattr(self, "details_ctrl") and self.details_ctrl:
                meta = {
                    "title": title,
                    "doc_type": doc_type,
                    "area": getattr(result, "area", ""),
                    "process": getattr(result, "process", ""),
                    "next_review": getattr(result, "next_review", ""),
                }
                self.details_ctrl.update_metadata(getattr(record, "doc_id", ""), meta)
        except Exception:
            # Keep import successful even if metadata update fails
            pass

        self._reload()

    def _edit_metadata(self) -> None:
        """Edit document metadata."""
        if not self.creation_ctrl:
            return

        rec = self._selected_record()
        if not rec:
            return

        if not MetadataDialog:
            messagebox.showinfo("Metadata", "Metadata dialog not available.", parent=self)
            return

        allowed = list(self._allowed_doc_types)
        dlg = MetadataDialog(self, rec, allowed_types=allowed)
        self.wait_window(dlg)
        result = getattr(dlg, "result", None)

        if result:
            metadata = {
                "title": result.title,
                "doc_type": result.doc_type,
                "area":  result.area,
                "process": result.process,
                "next_review":  result.next_review,
            }
            success, error_msg = self.creation_ctrl.update_metadata(rec.doc_id.value, metadata)

            if not success:
                messagebox.showerror("Fehler", error_msg or "Fehler beim Speichern", parent=self)
            else:
                self._reload()
                self._on_select()

    def _open_current(self) -> None:
        """Open current document file."""
        rec = self._selected_record()
        if not rec:
            return

        path = rec.current_file_path
        if not path or not os.path.isfile(path):
            messagebox.showerror(
                title=(T("documents.open.error") or "Öffnen fehlgeschlagen"),
                message=T("documents.open.nofile") or "Datei nicht gefunden.",
                parent=self
            )
            return

        try:
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            elif os.name == "posix":
                import subprocess
                subprocess. Popen(["xdg-open", path])
            else:
                messagebox.showinfo("Open", path, parent=self)
        except Exception as ex:
            messagebox.showerror(title=(T("documents.open.error") or "Open failed"), message=str(ex), parent=self)

    def _copy(self) -> None:
        """Copy EFFECTIVE document to destination."""
        rec = self._selected_record()
        if not rec or rec.status != DocumentStatus.EFFECTIVE:
            return

        dest_dir = filedialog.askdirectory(parent=self, title=(T("documents.copy.choose_dest") or "Zielordner wählen"))
        if not dest_dir:
            return

        try:
            out = self._repo.copy_to_destination(rec.doc_id.value, dest_dir)
            if out:
                messagebox.showinfo(
                    title=(T("documents.copy.ok") or "Kopie erstellt"),
                    message=(T("documents.copy.done") or "Kopie erstellt in: ") + out,
                    parent=self
                )
        except Exception as ex:
            messagebox.showerror("Copy", str(ex), parent=self)

    # ================================================================== ASSIGNMENTS
    def _assign_roles(self, force: bool = False) -> bool:
        """Open role assignment dialog."""
        rec = self._selected_record()
        if not rec or not self.assignment_ctrl:
            return False

        current = self.assignment_ctrl.get_assignees(rec.doc_id. value)
        users = self. assignment_ctrl.get_available_users()

        if force or not any(current. get(k) for k in ("AUTHOR", "REVIEWER", "APPROVER")):
            if AssignRolesDialog:
                dlg = AssignRolesDialog(self, users=users, current=current)
                self.wait_window(dlg)
                result = getattr(dlg, "result", None)
                if not result:
                    return False

                assignments = Assignments(
                    authors=result.get("AUTHOR", []),
                    reviewers=result.get("REVIEWER", []),
                    approvers=result.get("APPROVER", [])
                )
            else:
                # Fallback:  simple dialogs
                authors = simpledialog.askstring("Rollen", "Bearbeiter (',' getrennt):", parent=self) or ""
                reviewers = simpledialog.askstring("Rollen", "Prüfer (',' getrennt):", parent=self) or ""
                approvers = simpledialog.askstring("Rollen", "Freigeber (',' getrennt):", parent=self) or ""
                assignments = Assignments(
                    authors=[s.strip() for s in authors.split(",") if s.strip()],
                    reviewers=[s.strip() for s in reviewers.split(",") if s.strip()],
                    approvers=[s.strip() for s in approvers.split(",") if s.strip()],
                )

            # Validate and save
            success, error_msg = self.assignment_ctrl.set_assignees(rec.doc_id. value, assignments)
            if not success:
                messagebox.showerror(T("documents.assign.err") or "Fehler", error_msg or "Fehler", parent=self)
                return False

        return True

    # ================================================================== HELPERS
    def _ask_reason(self, title: str) -> Optional[str]:
        """Ask for reason (change note)."""
        s = simpledialog.askstring(
            T("documents.ask.reason. title") or "Begründung",
            (T("documents.ask.reason") or "Bitte eine kurze Begründung eingeben:") + f"\n({title})",
            parent=self
        )
        if s is None:
            return None
        s = s.strip()
        if not s:
            return None
        return s

    def _interactive_sign(self, pdf_path: str, reason: str) -> Optional[str]:
        """Interactive PDF signing via signature module."""
        try:
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