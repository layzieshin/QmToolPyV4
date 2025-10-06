# documents/logic/wordmeta_bridge.py
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Tuple

from word_meta.logic.metadata_extractor import get_document_metadata  # type: ignore


def _as_str(x: Any) -> str:
    return "" if x is None else str(x)


def _parse_dt(x: Any) -> datetime | None:
    if isinstance(x, datetime):
        return x
    s = _as_str(x).strip()
    if not s:
        return None
    s = s.replace(" ", "T").replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _to_int_or_none(x: Any) -> int | None:
    try:
        s = _as_str(x).strip()
        if not s:
            return None
        return int(float(s))  # deckt "3", 3, "3.0" ab
    except Exception:
        return None


def extract_core_and_comments(docx_path: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Map word_meta DocumentMetadata to (core_dict, comments_list) for repository use.
    core_dict keys include: title, subject, category, keywords, author, last_modified_by,
                            comments, created, modified, revision, version
    comments_list items: {"author": str, "date": datetime|None, "text": str}
    """
    md = get_document_metadata(docx_path)
    d = md.to_dict()  # {"core": {..., "review_comments":[...]}, ...}

    core_src: Dict[str, Any] = d.get("core", {}) or {}
    core: Dict[str, Any] = {
        "title": _as_str(core_src.get("title")),
        "subject": _as_str(core_src.get("subject")),
        "category": _as_str(core_src.get("category")),
        "keywords": _as_str(core_src.get("keywords")),
        "author": _as_str(core_src.get("author")),
        "last_modified_by": _as_str(core_src.get("last_modified_by")),
        "comments": _as_str(core_src.get("comments")),       # Core-Property "Comments"
        "created": _parse_dt(core_src.get("created")),
        "modified": _parse_dt(core_src.get("modified")),
        "revision": _to_int_or_none(core_src.get("revision")),  # ← sauber normalisiert
        "version": _as_str(core_src.get("version")),            # ← ebenfalls verfügbar
    }

    comments_raw = core_src.get("review_comments") or []
    comments: List[Dict[str, Any]] = []
    if isinstance(comments_raw, list):
        for c in comments_raw:
            if isinstance(c, dict):
                comments.append({
                    "author": _as_str(c.get("author")),
                    "date": _parse_dt(c.get("date")),
                    "text": _as_str(c.get("text")).strip(),
                })

    return core, comments
