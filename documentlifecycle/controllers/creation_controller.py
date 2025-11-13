"""
===============================================================================
CreationController – Import & Neu-aus-Vorlage mit editierbaren Metadaten
-------------------------------------------------------------------------------
Zweck
    - Import: .docx kopieren, Defaults aus Dateiname ableiten, Metadaten-Dialog
      anzeigen (editierbar), Datensatz anlegen, Liste neu laden & selektieren.
    - Neu aus Vorlage: .docx erstellen, Defaults ableiten, Dialog, Datensatz anlegen.

Design / SRP
    - UI-orientierte Orchestrierung; Persistenz macht DocumentCreationService.
    - T-Keys tragen das Präfix "documentlifecycle.".
    - Defensiv: Keine harten Abhängigkeiten auf AppContext (NullProvider-Fallback).
===============================================================================
"""
from __future__ import annotations
from typing import Optional, Protocol
from tkinter import messagebox

try:
    from core.common.app_context import T  # type: ignore
except Exception:  # pragma: no cover
    def T(key: str) -> str: return ""

from documentlifecycle.logic.services.document_creation_service import DocumentCreationService
from documentlifecycle.gui.dialogs.metadata_edit_dialog import MetadataEditDialog

# Optional: AppContext-Userprovider (falls im Projekt vorhanden)
try:
    from documentlifecycle.logic.adapters.appcontext_user_provider import AppContextUserProvider  # type: ignore
except Exception:  # pragma: no cover
    AppContextUserProvider = None  # type: ignore[misc,assignment]


class _CurrentUserProvider(Protocol):
    def current_user_id(self) -> Optional[int]: ...


class _NullUserProvider:
    def current_user_id(self) -> Optional[int]:
        return None


class CreationController:
    """
    Controller für Import- und Erstell-Workflows aus der Suchleiste.

    Parameter
    ---------
    view : Any
        Elternelement (Tk) / View mit 'controller' (Facade).
    creation_service : DocumentCreationService
        Kapselt Dateikopie, Default-Ableitung, DB-Registrierung.
    user_provider : Optional[_CurrentUserProvider]
        Liefert user_id für 'created_by' (NullProvider, wenn nicht vorhanden).
    """

    def __init__(self, view, creation_service: DocumentCreationService,
                 user_provider: Optional[_CurrentUserProvider] = None) -> None:
        self._view = view
        self._svc = creation_service
        if user_provider is not None:
            self._users = user_provider
        elif AppContextUserProvider is not None:  # type: ignore[truthy-bool]
            self._users = AppContextUserProvider()  # type: ignore[call-arg]
        else:
            self._users = _NullUserProvider()

    # ---------------- Hilfen ---------------- #
    def _facade(self):
        return getattr(self._view, "controller", None)

    def _info(self, title: str, message: str) -> None:
        """Zeigt eine Info-Meldung an (View.show_info > messagebox)."""
        try:
            fn = getattr(self._view, "show_info", None)
            if callable(fn):
                fn(title, message)
                return
        except Exception:
            pass
        try:
            messagebox.showinfo(title, message, parent=self._view)
        except Exception:
            pass

    def _edit_metadata(self, *, parent, dialog_title: str, initial: dict) -> Optional[dict]:
        """
        Öffnet den Metadaten-Dialog mit Initialwerten; gibt bearbeiteten Dict zurück
        oder None, wenn der Benutzer abbricht.
        """
        dlg = MetadataEditDialog(parent, title_text=dialog_title, initial=initial)
        return dlg.show_modal()

    # ---------------- Aktionen ---------------- #
    def action_import_docx(self) -> None:
        """
        Importiert eine vorhandene .docx, fragt editierbare Metadaten ab und
        legt einen Datensatz an. Danach wird die Liste neu geladen und selektiert.
        """
        try:
            parent = getattr(self._view, "winfo_toplevel", lambda: None)()

            copy_res = self._svc.import_docx_copy_only(parent=parent)
            if copy_res.cancelled:
                self._info(T("documentlifecycle.dialog.import.title") or "Import",
                           T("documentlifecycle.dialog.import.cancelled") or "Import abgebrochen")
                return
            if not copy_res.ok or not copy_res.dest_path:
                self._info(T("documentlifecycle.dialog.import.title") or "Import",
                           f"{T('documentlifecycle.errors.unexpected') or 'Unerwarteter Fehler'}: {copy_res.message}")
                return

            defaults = self._svc.derive_defaults_from_path(copy_res.dest_path, for_new=False)
            edited = self._edit_metadata(
                parent=parent,
                dialog_title=T("documentlifecycle.dialog.import.title") or "Import",
                initial={
                    "title": defaults.title,
                    "code": defaults.code,
                    "doc_type": defaults.doc_type,
                    "description": defaults.description,
                },
            )
            if edited is None:
                self._info(T("documentlifecycle.dialog.import.title") or "Import",
                           T("documentlifecycle.dialog.import.cancelled") or "Import abgebrochen")
                return

            try:
                uid = self._users.current_user_id()
            except Exception:
                uid = None

            new_id = self._svc.register_copied_docx_in_db(
                dest_path=copy_res.dest_path,
                created_by_user_id=uid,
                default_doc_type=edited.get("doc_type") or "OTHER",
                default_status="IN_REVIEW",
                title=edited.get("title") or "",
                code=edited.get("code"),
                description=edited.get("description", "") or "",
            )

            facade = self._facade()
            if facade and hasattr(facade, "load_document_list"):
                facade.load_document_list()
                if isinstance(new_id, int) and hasattr(facade, "on_select_document"):
                    facade.on_select_document(new_id)

            self._info(T("documentlifecycle.dialog.import.title") or "Import",
                       (T("documentlifecycle.dialog.import.success") or "Datei importiert: {path}")
                       .format(path=copy_res.dest_path))
        except Exception as exc:
            self._info(T("documentlifecycle.dialog.import.title") or "Import",
                       f"{T('documentlifecycle.errors.unexpected') or 'Unerwarteter Fehler'}: {type(exc).__name__}")

    def action_create_from_template(self) -> None:
        """
        Erstellt ein neues .docx aus Vorlage, fragt Metadaten ab und
        legt einen DRAFT-Datensatz an. Danach Reload & Selektion.
        """
        try:
            parent = getattr(self._view, "winfo_toplevel", lambda: None)()

            copy_res = self._svc.create_from_template(parent=parent)
            if copy_res.cancelled:
                self._info(T("documentlifecycle.dialog.create.title") or "Neu",
                           T("documentlifecycle.dialog.import.cancelled") or "Abgebrochen")
                return
            if not copy_res.ok or not copy_res.dest_path:
                self._info(T("documentlifecycle.dialog.create.title") or "Neu",
                           f"{T('documentlifecycle.errors.unexpected') or 'Unerwarteter Fehler'}: {copy_res.message}")
                return

            defaults = self._svc.derive_defaults_from_path(copy_res.dest_path, for_new=True)
            edited = self._edit_metadata(
                parent=parent,
                dialog_title=T("documentlifecycle.dialog.create.title") or "Neu aus Vorlage",
                initial={
                    "title": defaults.title,
                    "code": defaults.code,
                    "doc_type": defaults.doc_type,
                    "description": defaults.description,
                },
            )
            if edited is None:
                self._info(T("documentlifecycle.dialog.create.title") or "Neu",
                           T("documentlifecycle.dialog.import.cancelled") or "Abgebrochen")
                return

            try:
                uid = self._users.current_user_id()
            except Exception:
                uid = None

            new_id = self._svc.register_copied_docx_in_db(
                dest_path=copy_res.dest_path,
                created_by_user_id=uid,
                default_doc_type=edited.get("doc_type") or "OTHER",
                default_status="DRAFT",
                title=edited.get("title") or "",
                code=edited.get("code"),
                description=edited.get("description", "") or "",
            )

            facade = self._facade()
            if facade and hasattr(facade, "load_document_list"):
                facade.load_document_list()
                if isinstance(new_id, int) and hasattr(facade, "on_select_document"):
                    facade.on_select_document(new_id)

            self._info(T("documentlifecycle.dialog.create.title") or "Neu",
                       (T("documentlifecycle.dialog.create.success") or "Neues Dokument erstellt: {path}")
                       .format(path=copy_res.dest_path))
        except Exception as exc:
            self._info(T("documentlifecycle.dialog.create.title") or "Neu",
                       f"{T('documentlifecycle.errors.unexpected') or 'Unerwarteter Fehler'}: {type(exc).__name__}")
