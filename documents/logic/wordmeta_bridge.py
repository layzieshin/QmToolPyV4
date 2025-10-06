# documents/logic/wordmeta_bridge.py
"""
Bridge to use the central word_meta extractor inside the Documents feature.

- Reads core metadata + review comments via word_meta.logic.metadata_extractor.get_document_metadata
- Maps the structure returned by DocumentMetadata.to_dict():
    {
      "core": {
        ...,
        "review_comments": [{"id", "author", "date", "text"}, ...]
      },
      "extended": {...},
      "custom": [...],
      "file": {...}
    }

- Returns (core_dict, comments_list) in the shape expected by our repository:
    core_dict keys: title, subject, category, keywords, author, last_modified_by,
                    comments, created, modified, revision
    comments_list items: {"author": str, "date": datetime|None, "text": str}
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Tuple

# Import the exact extractor used in your module
from word_meta.logic.metadata_extractor import get_document_metadata  # type: ignore


def _as_str(x: Any) -> str:
    return "" if x is None else str(x)


def extract_core_and_comments(docx_path: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Use the word_meta extractor and adapt to the repository's expected shape.
    """
    md = get_document_metadata(docx_path)
    # We rely on the stable to_dict() contract of your DocumentMetadata model
    # where "core" contains classic properties and "review_comments".
    d = md.to_dict()  # -> {"core": {..., "review_comments":[...]}, "extended":..., "custom":..., "file":...}

    core_src: Dict[str, Any] = d.get("core", {}) or {}

    # ---- Map core fields 1:1 (names come from docx_core_reader) ----
    core: Dict[str, Any] = {
        "title": _as_str(core_src.get("title")),
        "subject": _as_str(core_src.get("subject")),
        "category": _as_str(core_src.get("category")),
        "keywords": _as_str(core_src.get("keywords")),
        "author": _as_str(core_src.get("author")),
        "last_modified_by": _as_str(core_src.get("last_modified_by")),
        "comments": _as_str(core_src.get("comments")),  # this is the "core-properties comments" field
        "created": core_src.get("created"),             # typically datetime from python-docx
        "modified": core_src.get("modified"),
        "revision": core_src.get("revision"),
    }

    # ---- Map review comments list (exactly as word_meta provides it) ----
    comments_src = core_src.get("review_comments") or []
    comments: List[Dict[str, Any]] = []
    if isinstance(comments_src, list):
        for c in comments_src:
            if not isinstance(c, dict):
                continue
            comments.append(
                {
                    "author": _as_str(c.get("author")),
                    # docx_comments_reader already returns datetime for 'date'
                    # if parsing succeeded; we pass it through unchanged.
                    "date": c.get("date") if isinstance(c.get("date"), datetime) else None,
                    "text": _as_str(c.get("text")).strip(),
                }
            )

    return core, comments
