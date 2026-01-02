"""View state DTO.

TODO: Add UI-specific flags derived from policy services.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ViewState:
    """Derived UI state for a document."""

    can_edit: bool
    can_submit_review: bool
    can_approve: bool
    can_publish: bool
    can_archive: bool
