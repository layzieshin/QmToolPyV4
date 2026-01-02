"""UI state service (no IO).

TODO: Combine policy services to derive UI states.
"""
from __future__ import annotations

from documents.dto.view_state import ViewState


class UIStateService:
    """Derive view state flags from policy evaluation."""

    def build_state(self) -> ViewState:
        """Build a default view state placeholder."""
        return ViewState(
            can_edit=False,
            can_submit_review=False,
            can_approve=False,
            can_publish=False,
            can_archive=False,
        )
