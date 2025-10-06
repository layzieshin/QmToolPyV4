from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

# Readers
from word_meta.logic.docx_core_reader import read_docx_core_properties
from word_meta.logic.docx_comments_reader import read_docx_comments
from word_meta.logic.docx_app_reader import read_docx_app_properties
from word_meta.logic.docx_custom_reader import read_docx_custom_properties

# Models
from word_meta.models.custom_property import CustomProperty
from word_meta.models.document_metadata import DocumentMetadata


def _serialize_comments(comments) -> List[Dict[str, Any]]:
    return [
        {
            "id": c.comment_id,
            "author": c.author,
            "date": c.date,
            "text": c.text,
        }
        for c in comments
    ]


def _serialize_custom(props: List[CustomProperty]) -> List[Dict[str, Any]]:
    return [
        {"name": p.name, "type": p.value_type, "value": p.value, "pid": p.pid}
        for p in props
    ]


def _file_info(path: str) -> Dict[str, Any]:
    try:
        p = Path(path)
        st = p.stat()
        return {
            "path": str(p),
            "size_bytes": st.st_size,
            "modified_ts": st.st_mtime,
            "created_ts": st.st_ctime,
        }
    except Exception:
        return {"path": path}


def get_document_metadata(docx_path: str) -> DocumentMetadata:
    """
    High-level extractor for DOCX:
    - core: classic core properties + review_comments (list)
    - extended: extended/app properties (pages, words, application, ...)
    - custom: user-defined custom properties
    - file: basic file info
    """
    core = read_docx_core_properties(docx_path)
    core["review_comments"] = _serialize_comments(read_docx_comments(docx_path))

    extended = read_docx_app_properties(docx_path)
    custom = _serialize_custom(read_docx_custom_properties(docx_path))
    file_sec = _file_info(docx_path)

    return DocumentMetadata(
        core=core,
        extended=extended,
        custom=custom,
        file=file_sec,
        other={}
    )
