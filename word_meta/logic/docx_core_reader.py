from __future__ import annotations

from typing import Any, Dict
from docx import Document

def _safe(cp, attr: str, default=None):
    try:
        return getattr(cp, attr)
    except Exception:
        return default

def read_docx_core_properties(docx_path: str) -> Dict[str, Any]:
    """
    Read classic core properties via python-docx.
    """
    doc = Document(docx_path)
    cp = doc.core_properties
    return {
        "title": _safe(cp, "title", "") or "",
        "subject": _safe(cp, "subject", "") or "",
        "author": _safe(cp, "author", "") or "",
        "last_modified_by": _safe(cp, "last_modified_by", "") or "",
        "created": _safe(cp, "created", None),
        "modified": _safe(cp, "modified", None),
        "category": _safe(cp, "category", "") or "",
        "comments": _safe(cp, "comments", "") or "",
        "keywords": _safe(cp, "keywords", "") or "",
        "version": _safe(cp, "version", "") or "",
        "revision": _safe(cp, "revision", None),
        "last_printed": _safe(cp, "last_printed", None),
        "identifier": _safe(cp, "identifier", "") or "",
        "language": _safe(cp, "language", "") or "",
        "content_status": _safe(cp, "content_status", "") or "",
    }
