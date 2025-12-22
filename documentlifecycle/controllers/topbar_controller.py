"""documentlifecycle/controllers/topbar_controller.py

===============================================================================
TopbarController – anemic UI controller for SearchBar (Import / New from template)
-------------------------------------------------------------------------------
Goal (explicit project rule)
    - Controllers are *anemic*: they only forward UI events to exactly ONE
      service call.
    - No business logic, no multi-step orchestration, no persistence.

This controller is connected to:
    documentlifecycle/gui/search_bar.py

The SearchBar expects the following methods on its controller:
    - action_import_docx()
    - action_create_from_template()

Implementation note
    The complete flow (file selection/copy + metadata dialog + DB insert + UI
    refresh) lives inside DocumentCreationService.
===============================================================================
"""

from __future__ import annotations

from typing import Any, Optional

from documentlifecycle.logic.services.document_creation_service import DocumentCreationService


class TopbarController:
    """Anemic controller for SearchBar.

    The only responsibility is to forward button clicks to the creation service.

    Parameters
    ----------
    view:
        The parent view / facade (usually DocumentLifecycleView).
        The service will use this view to show messages and trigger refresh.
    creation_service:
        Service implementing the *entire* import/create flow.
    user_provider:
        Optional provider passed through to the service to attribute created_by.
        The service supports multiple provider shapes (see its docstring).
    """

    def __init__(
        self,
        *,
        view: Any,
        creation_service: Optional[DocumentCreationService] = None,
        user_provider: Any | None = None,
    ) -> None:
        self._view = view
        self._svc = creation_service or DocumentCreationService()
        self._users = user_provider

    # ---------------------------------------------------------------------
    # Button actions (SearchBar wires these method names)
    # ---------------------------------------------------------------------
    def action_import_docx(self) -> None:
        """Forward: Import DOCX button -> one service call."""
        self._svc.run_import_flow(view=self._view, user_provider=self._users)

    def action_create_from_template(self) -> None:
        """Forward: New from template button -> one service call."""
        self._svc.run_create_from_template_flow(view=self._view, user_provider=self._users)
