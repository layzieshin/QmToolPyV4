"""ControlsState DTO for UI button enablement."""

from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class ControlsState:
    """
    UI state for button enablement and text.

    Immutable DTO - computed by DocumentDetailsController.
    """

    can_open:  bool
    can_copy: bool
    can_assign_roles: bool
    can_archive: bool
    can_next: bool
    can_back_to_draft: bool
    can_toggle_workflow: bool
    workflow_text: str
    next_text: str

    @staticmethod
    def disabled() -> "ControlsState":
        """Factory for fully disabled state (no document selected)."""
        return ControlsState(
            can_open=False,
            can_copy=False,
            can_assign_roles=False,
            can_archive=False,
            can_next=False,
            can_back_to_draft=False,
            can_toggle_workflow=False,
            workflow_text="—",
            next_text="—",
        )