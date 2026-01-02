"""documents/enum/document_action.py
================================

Canonical action identifiers used by the documents feature policies.

The UI and services should use these ids instead of hardcoding strings.
"""
from __future__ import annotations

from enum import Enum


class DocumentAction(str, Enum):
    """Supported document actions."""

    EDIT_METADATA = "edit_metadata"
    EDIT_CONTENT = "edit_content"

    SUBMIT_REVIEW = "submit_review"
    APPROVE = "approve"
    PUBLISH = "publish"

    CREATE_REVISION = "create_revision"
    OBSOLETE = "obsolete"
    ARCHIVE = "archive"

    SIGN = "sign"
