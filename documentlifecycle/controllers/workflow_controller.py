"""
===============================================================================
WorkflowController – thin MVC controller delegating to Services (SRP)
-------------------------------------------------------------------------------
This controller now only:
  - receives UI events from BottomBar,
  - delegates to services,
  - shows user feedback (via facade),
  - refreshes list/details,
  - opens the roles dialog after start/cancel (UI responsibility).

Public method names match your BottomBar wiring:
  action_open_read / action_read
  action_print
  action_edit
  action_workflow_start
  action_workflow_cancel / action_workflow_abort
  action_finish_and_sign
  action_archive
  action_edit_roles
===============================================================================
"""
from __future__ import annotations

from typing import Optional, Protocol, Any

try:
    from core.common.app_context import T  # type: ignore
except Exception:  # pragma: no cover
    def T(_key: str) -> str: return ""

from documentlifecycle.logic.services.actions.reading_service import ReadingService
from documentlifecycle.logic.services.actions.printing_service import PrintingService
from documentlifecycle.logic.services.actions.editing_service import EditingService
from documentlifecycle.logic.services.actions.workflow_service import WorkflowService


class _Facade(Protocol):
    def load_document_list(self) -> None: ...
    def on_select_document(self, doc_id: int) -> None: ...
    def show_info(self, title: str, message: str) -> None: ...
    def show_error(self, title: str, message: str) -> None: ...
    @property
    def view(self) -> Any: ...


class WorkflowController:
    """Delegating controller for BottomBar actions."""

    def __init__(self, *, facade: _Facade, ui_service: Any | None = None, user_provider: Any | None = None) -> None:
        self._facade = facade
        self._users = user_provider

        # Services (grouped under logic/services/actions/)
        self._svc_read = ReadingService()
        self._svc_print = PrintingService()
        self._svc_edit = EditingService()
        self._svc_flow = WorkflowService()

        self._doc_id: Optional[int] = None

    # ---------- selection ----------
    def set_current_document(self, doc_id: Optional[int]) -> None:
        self._doc_id = doc_id

    # ---------- actions ----------
    def action_open_read(self) -> None:
        self.action_read()

    def action_read(self) -> None:
        if not self._doc_id:
            return
        try:
            self._svc_read.open_for_read(document_id=self._doc_id, facade=self._facade)
        except Exception as exc:
            self._facade.show_error(T("documentlifecycle.document.read") or "Read", str(exc))

    def action_print(self) -> None:
        if not self._doc_id:
            return
        try:
            self._svc_print.print_controlled_copy(document_id=self._doc_id, user_provider=self._users)
            self._facade.show_info(T("documentlifecycle.document.print") or "Print",
                                   T("documentlifecycle.print.done") or "Print job triggered.")
        except Exception as exc:
            self._facade.show_error(T("documentlifecycle.document.print") or "Print", str(exc))

    def action_edit(self) -> None:
        if not self._doc_id:
            return
        try:
            self._svc_edit.open_for_edit(document_id=self._doc_id)
        except Exception as exc:
            self._facade.show_info(T("documentlifecycle.document.edit") or "Edit", str(exc))

    def action_workflow_start(self) -> None:
        if not self._doc_id:
            return
        try:
            self._svc_flow.start(document_id=self._doc_id)
        finally:
            self._refresh()
            self.action_edit_roles()  # UI responsibility

    def action_workflow_cancel(self) -> None:
        self.action_workflow_abort()

    def action_workflow_abort(self) -> None:
        if not self._doc_id:
            return
        try:
            self._svc_flow.cancel(document_id=self._doc_id)
        finally:
            self._refresh()
            self.action_edit_roles()

    def action_finish_and_sign(self) -> None:
        if not self._doc_id:
            return
        try:
            self._svc_flow.finish_and_sign(document_id=self._doc_id)
        finally:
            self._refresh()

    def action_archive(self) -> None:
        if not self._doc_id:
            return
        try:
            uid = None
            if self._users and hasattr(self._users, "current_user_id"):
                uid = self._users.current_user_id()
            elif self._users and hasattr(self._users, "get_current_user"):
                u = self._users.get_current_user()
                uid = getattr(u, "id", None)
            self._svc_flow.archive(document_id=self._doc_id, archived_by=uid)
        finally:
            self._refresh()

    def action_edit_roles(self) -> None:
        """Open roles dialog if present; otherwise show info."""
        try:
            from documentlifecycle.gui.dialogs.roles_dialog import RolesDialog  # type: ignore
            dlg = RolesDialog(self._facade.view, document_id=self._doc_id)
            dlg.show_modal()
        except Exception:
            self._facade.show_info(
                T("documentlifecycle.document.roles.edit") or "Edit roles",
                T("documentlifecycle.roles.dialog_stub") or "Roles dialog not integrated yet.",
            )

    # ---------- refresh ----------
    def _refresh(self) -> None:
        try:
            self._facade.load_document_list()
        except Exception:
            pass
        if self._doc_id:
            try:
                self._facade.on_select_document(self._doc_id)
            except Exception:
                pass
