"""
===============================================================================
DocumentDetailsController – Details rendern & Bottom-Bar-State anwenden
-------------------------------------------------------------------------------
Zweck
    - Auf Listenselektion reagieren, Details laden und anzeigen.
    - Policy-/UI-State berechnen lassen und in die BottomBar spiegeln.

Design / SRP
    - Reine UI-Vermittlung (keine Persistenz, keine Signatur-/Workflow-Logik).
    - Defensiv: Unterschiedliche View-Methoden werden toleriert.
===============================================================================
"""
from __future__ import annotations
from typing import Optional


class DocumentDetailsController:
    """
    Vermittler zwischen Detail-Service und View/BottomBar.

    Parameter
    ---------
    view : Any
        GUI-View; sollte entweder 'render_document_details(details)' bereitstellen
        oder eine 'detail_panel' mit 'set_details(doc_id, details)' besitzen.
    doc_service : Any
        Liefert 'get_details(doc_id)' -> dict | None.
    ui_state_service : Any
        Liefert 'compute(doc_id, user, workflow_starter_id)' -> state-Objekt.
    user_provider : Any
        Liefert 'get_current_user()' (für spätere Policy-Prüfungen).
    """

    def __init__(self, view, doc_service, ui_state_service, user_provider) -> None:
        self._view = view
        self._doc_svc = doc_service
        self._ui_svc = ui_state_service
        self._user_provider = user_provider

    # --------------------------------------------------------------------- #
    # Öffentliche API
    # --------------------------------------------------------------------- #
    def on_select_document(self, doc_id: int, workflow_starter_id: Optional[int]) -> None:
        """
        Details laden, rendern und BottomBar-UI-Status anwenden.

        Parameters
        ----------
        doc_id : int
            Selektierte Dokument-ID.
        workflow_starter_id : Optional[int]
            User-ID des Workflow-Starters (für Abbruch-Policies).
        """
        details = self._doc_svc.get_details(doc_id)

        # 1) Details in der View anzeigen (beide Varianten werden unterstützt)
        try:
            # bevorzugt konsolidierte Render-Methode
            render = getattr(self._view, "render_document_details", None)
            if callable(render):
                render(details or None)
            else:
                # Fallback: klassisches Panel mit set_details(...)
                panel = getattr(self._view, "detail_panel", None)
                setter = getattr(panel, "set_details", None)
                if callable(setter):
                    setter(doc_id, details or {})
        except Exception:
            pass

        # 2) Policy-/UI-State anwenden (sichtbare Buttons usw.)
        try:
            user = self._user_provider.get_current_user()
        except Exception:
            user = None

        try:
            state = self._ui_svc.compute(
                doc_id=doc_id,
                user=user,
                workflow_starter_id=workflow_starter_id,
            )
            self._apply_ui_state(state)
        except Exception:
            # Absichtlich leise – UI soll nicht durch State-Berechnung blockieren.
            pass

    # --------------------------------------------------------------------- #
    # Interne Helfer
    # --------------------------------------------------------------------- #
    def _apply_ui_state(self, state) -> None:
        """
        Angewiesenen UI-State auf die BottomBar übertragen (defensiv).
        Erwartete Attribute im 'state':
            - show_workflow_start: bool
            - show_workflow_abort (oder show_workflow_cancel): bool
            - show_sign, show_archive, show_edit_roles: bool
        """
        bb = getattr(self._view, "bottom_bar", None)
        if not bb:
            return

        # Workflow-Buttons (Toggle)
        try:
            if getattr(state, "show_workflow_start", False) and hasattr(bb, "show_workflow_start"):
                bb.show_workflow_start()
            # akzeptiere beide Bezeichner, leite aber stets auf 'cancel' weiter
            show_abort = getattr(state, "show_workflow_abort", False) or getattr(state, "show_workflow_cancel", False)
            if show_abort:
                if hasattr(bb, "show_workflow_cancel"):
                    bb.show_workflow_cancel()
                elif hasattr(bb, "show_workflow_abort"):  # Alt
                    bb.show_workflow_abort()
        except Exception:
            pass

        # Granulare Sichtbarkeit
        for meth_name, flag in (
            ("set_sign_visible", getattr(state, "show_sign", False)),
            ("set_archive_visible", getattr(state, "show_archive", False)),
            ("set_edit_roles_visible", getattr(state, "show_edit_roles", False)),
        ):
            fn = getattr(bb, meth_name, None)
            if callable(fn):
                try:
                    fn(flag)
                except Exception:
                    pass
