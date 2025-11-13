"""
===============================================================================
File Dialogs Adapter – tiny wrapper around Tk file dialogs
-------------------------------------------------------------------------------
Purpose:
    Keep tkinter UI imports out of services and provide a single place to
    configure filters and parent handling.
===============================================================================
"""
from __future__ import annotations
from typing import Optional, Any

try:
    import tkinter as tk
    from tkinter import filedialog
except Exception:  # pragma: no cover
    tk = None  # type: ignore
    filedialog = None  # type: ignore


def _parent_if_valid(parent: Any | None):
    if filedialog is None or tk is None:
        return None
    try:
        return parent if isinstance(parent, tk.Misc) else None
    except Exception:
        return None


def ask_open_docx(parent: Any | None = None) -> Optional[str]:
    """
    Show an 'open file' dialog for .docx files. Returns a filesystem path or
    None if the user cancelled.
    """
    if filedialog is None:
        return None
    try:
        return filedialog.askopenfilename(
            parent=_parent_if_valid(parent),
            title="Select Word document",
            filetypes=[("Word Documents", "*.docx"), ("All files", "*.*")],
        ) or None
    except Exception:
        return None


def ask_open_template(parent: Any | None = None) -> Optional[str]:
    """
    Show an 'open file' dialog for templates (.dotx/.docx). Returns a path or None.
    """
    if filedialog is None:
        return None
    try:
        return filedialog.askopenfilename(
            parent=_parent_if_valid(parent),
            title="Select Word template",
            filetypes=[
                ("Word Template", "*.dotx"),
                ("Word Document", "*.docx"),
                ("All files", "*.*"),
            ],
        ) or None
    except Exception:
        return None
