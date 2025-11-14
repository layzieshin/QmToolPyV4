"""
===============================================================================
Actions Controller – non-workflow actions (read/print/archive/edit roles)
-------------------------------------------------------------------------------
Purpose:
    - Provide thin UI actions for reading, printing, archiving, and editing
      roles. Policies and persistence will be handled by services later.

Contract to the View:
    - Uses view.show_info/show_warning for user feedback.
===============================================================================
"""
from __future__ import annotations
from typing import Optional

try:
    from core.common.app_context import T  # type: ignore
except Exception:  # pragma: no cover
    def T(_key: str) -> str: return ""


class DocumentActionsController:
    """
    Controller grouping non-workflow actions.

    Responsibilities:
        - Keep the UI responsive with clear messages.
        - Defer all domain decisions to dedicated services later.

    Excludes:
        - No direct file opening/printing; will be added behind services.
    """

    def __init__(self, view) -> None:
        """
        Parameters
        ----------
        view : Any
            The GUI view exposing popup helpers 'show_info' and 'show_warning'.
        """
        self._view = view

    def action_read(self, current_doc_id: Optional[int]) -> None:
        """Open a document for reading (placeholder)."""
        if not current_doc_id:
            self._view.show_warning(T("document.read") or "Lesen", "Bitte zuerst ein Dokument auswählen.")
            return
        self._view.show_info(T("document.read") or "Lesen", f"Would open doc #{current_doc_id} (not implemented).")

    def action_print(self, current_doc_id: Optional[int]) -> None:
        """Print a document (placeholder)."""
        if not current_doc_id:
            self._view.show_warning(T("document.print") or "Drucken", "Bitte zuerst ein Dokument auswählen.")
            return
        self._view.show_info(T("document.print") or "Drucken", f"Would print doc #{current_doc_id} (not implemented).")

    def action_archive(self, current_doc_id: Optional[int]) -> None:
        """Archive a published document (placeholder)."""
        if not current_doc_id:
            self._view.show_warning(T("document.archive") or "Archivieren", "Bitte zuerst ein Dokument auswählen.")
            return
        self._view.show_info(T("document.archive") or "Archivieren", "Archive (placeholder).")

    def action_edit_roles(self, current_doc_id: Optional[int]) -> None:
        """Open role editor for the selected document (placeholder)."""
        if not current_doc_id:
            self._view.show_warning(T("document.roles.edit") or "Rollen bearbeiten", "Bitte zuerst ein Dokument auswählen.")
            return
        self._view.show_info(T("document.roles.edit") or "Rollen bearbeiten", "Open role editor (placeholder).")
