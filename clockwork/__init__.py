"""
Clockwork feature package initializer.

Provides factory functions that your main window / feature loader can call to
create the clock view and its settings view without hard-coding internals.

Both factories accept a `parent` Tk container and an optional `app_context`.
The latter is not required but supported to align with your architecture.
"""

from typing import Optional
import tkinter as tk

from .gui.clock_widget import ClockWidget
from .gui.settings_widget import ClockworkSettingsWidget


def get_feature_name() -> str:
    """
    Human readable feature name (used e.g. for navigation labels).

    Returns:
        str: The localized or default feature name.
    """
    return _t("clockwork.title", "Clockwork")


def create_feature_view(parent: tk.Misc, app_context: Optional[object] = None) -> tk.Frame:
    """
    Factory for the main clock view.

    Args:
        parent (tk.Misc): Tk container to mount the widget onto.
        app_context (object, optional): Application context (if your app passes one).

    Returns:
        tk.Frame: A fully wired clock widget.
    """
    frame = ClockWidget(parent, app_context=app_context)
    return frame


def create_settings_view(parent: tk.Misc, app_context: Optional[object] = None) -> tk.Frame:
    """
    Factory for the clockwork settings view.

    Args:
        parent (tk.Misc): Tk container to mount the widget onto.
        app_context (object, optional): Application context (if your app passes one).

    Returns:
        tk.Frame: The settings editor frame.
    """
    frame = ClockworkSettingsWidget(parent, app_context=app_context)
    return frame


# --- Internal helpers -------------------------------------------------------

def _t(key: str, default: str) -> str:
    """
    Very defensive translation helper:
    - Try your LocaleManager if present (core.locale.LocaleManager).
    - Fall back to the provided default.

    Args:
        key (str): Translation key
        default (str): Fallback string

    Returns:
        str: Translated or default text
    """
    try:
        # Try a few common access patterns without adding a hard dependency
        from core.locale import LocaleManager  # type: ignore
        try:
            lm = LocaleManager.instance()  # preferred
        except Exception:
            try:
                lm = LocaleManager.get_instance()  # alternative
            except Exception:
                lm = None
        if lm is not None:
            return lm.t(key) or default
    except Exception:
        pass
    return default
