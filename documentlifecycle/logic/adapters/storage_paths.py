"""
===============================================================================
Storage Paths Adapter – resolve & prepare filesystem locations
-------------------------------------------------------------------------------
Purpose:
    Centralize path selection for the Document Lifecycle module.
    - Reads optional paths from host Settings (if available).
    - Provides sensible defaults and ensures directories exist.

Notes:
    This module does NOT know about databases. It is safe to use from Services.
===============================================================================
"""
from __future__ import annotations
import os
from pathlib import Path

try:
    # Optional: host settings manager (if available in the project)
    from core.settings.logic.settings_manager import SettingsManager  # type: ignore
except Exception:  # pragma: no cover
    SettingsManager = None  # type: ignore


def _expand(path: str) -> Path:
    """Expand ~ and environment variables; return as Path."""
    return Path(os.path.expandvars(os.path.expanduser(path))).resolve()


def _ensure_dir(p: Path) -> Path:
    """Create directory if missing (parents ok) and return it."""
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_documents_root() -> Path:
    """
    Return the root folder for documents. Preference order:
        1) SettingsManager key 'document_storage_root'
        2) Default: ~/Documents/QMTool/Docs
    The directory is created if missing.
    """
    if SettingsManager:
        try:
            root = SettingsManager.get("document_storage_root")  # type: ignore[attr-defined]
            if isinstance(root, str) and root.strip():
                return _ensure_dir(_expand(root))
        except Exception:
            pass
    return _ensure_dir(_expand("~/Documents/QMTool/Docs"))


def get_inbox_dir() -> Path:
    """Inbox directory used by import flow. Example: <root>/inbox"""
    return _ensure_dir(get_documents_root() / "inbox")


def get_drafts_dir() -> Path:
    """Drafts directory used by 'create from template'. Example: <root>/drafts"""
    return _ensure_dir(get_documents_root() / "drafts")


def get_templates_root() -> Path:
    """
    Optional templates directory (for a future template picker).
    Preference:
        1) SettingsManager key 'document_template_root'
        2) Default: <root>/templates
    """
    if SettingsManager:
        try:
            root = SettingsManager.get("document_template_root")  # type: ignore[attr-defined]
            if isinstance(root, str) and root.strip():
                return _ensure_dir(_expand(root))
        except Exception:
            pass
    return _ensure_dir(get_documents_root() / "templates")
