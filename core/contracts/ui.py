"""core/contracts/ui.py
====================

UI-facing contracts for discoverable features.

Important:
- The current framework loads UI classes dynamically and injects dependencies by
  matching constructor parameter names against the AppContext service registry.
- These interfaces are the *future-proof* public API for UI classes. Existing
  views may not implement them yet; adoption is done incrementally.

We keep the interface minimal and lifecycle-oriented to avoid over-constraining
Tkinter usage.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IModuleView(ABC):
    """A discoverable main view of a feature (navigation entry)."""

    @abstractmethod
    def on_show(self) -> None:
        """Called when the view becomes active/visible in the main window."""

    @abstractmethod
    def on_hide(self) -> None:
        """Called when the view is removed/hidden."""

    @abstractmethod
    def dispose(self) -> None:
        """Release resources (threads, file handles, timers). Must be idempotent."""


class ISettingsTab(ABC):
    """A settings UI tab for a feature."""

    @abstractmethod
    def load_settings(self) -> None:
        """Load current values from the settings service and update widgets."""

    @abstractmethod
    def save_settings(self) -> None:
        """Persist current widget values using the settings service."""

    @abstractmethod
    def reset_to_defaults(self) -> None:
        """Reset settings for the feature to defaults (UI + persistence)."""
