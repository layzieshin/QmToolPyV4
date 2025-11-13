"""
===============================================================================
UI State (Document Lifecycle) – View-facing flags & hints
-------------------------------------------------------------------------------
Purpose:
    Provide a minimal, serializable structure that expresses which UI elements
    should be visible or enabled in the Document Lifecycle view. This module
    is strictly view-oriented and holds no business logic.

Ownership:
    Instances are produced by services (e.g., UIStateService) based on domain
    rules and user permissions (policies). The view consumes this state to
    show/hide buttons and surface contextual hints.

SRP:
    - No repository or policy imports here except typing primitives.
===============================================================================
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(slots=True)
class DocumentLifecycleUIState:
    """
    Encapsulates visibility and hinting for the lifecycle view.

    Fields
    ------
    show_read : bool
        Whether the 'Read' action should be visible.
    show_print : bool
        Whether the 'Print' action should be visible.
    show_sign : bool
        Whether the 'Finish & Sign' action should be visible.
    show_archive : bool
        Whether the 'Archive' action should be visible.
    show_edit_roles : bool
        Whether the 'Edit Roles' action should be visible.
    show_workflow_start : bool
        Whether the 'Start workflow' button (green) should be visible.
    show_workflow_abort : bool
        Whether the 'Abort workflow' button (red) should be visible.
    highlight_expired : bool
        If True, the document's validity is exceeded (view may highlight).
    can_extend_without_change : bool
        If True, settings/policy allow a 2-year extension without content change.
    info_hint : str
        Optional textual hint (e.g., "Active phase: Reviewer").
    """
    show_read: bool = True
    show_print: bool = True
    show_sign: bool = False
    show_archive: bool = False
    show_edit_roles: bool = False
    show_workflow_start: bool = True
    show_workflow_abort: bool = False
    highlight_expired: bool = False
    can_extend_without_change: bool = False
    info_hint: str = ""
