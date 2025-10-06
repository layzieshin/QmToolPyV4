from __future__ import annotations

import zipfile
from typing import Any, Dict, Optional
import xml.etree.ElementTree as ET

# Extended properties namespace
EP = "{http://schemas.openxmlformats.org/officeDocument/2006/extended-properties}"

def _text(root: ET.Element, tag: str) -> Optional[str]:
    node = root.find(f"{EP}{tag}")
    return (node.text.strip() if node is not None and node.text else None)

def _int(root: ET.Element, tag: str) -> Optional[int]:
    t = _text(root, tag)
    if t is None:
        return None
    try:
        return int(t)
    except Exception:
        return None

def _bool(root: ET.Element, tag: str) -> Optional[bool]:
    t = _text(root, tag)
    if t is None:
        return None
    return t.lower() in ("true", "1")

def read_docx_app_properties(path: str) -> Dict[str, Any]:
    """
    Read docProps/app.xml (extended properties) and return a dict with
    human-friendly keys matching common expectations.
    """
    out: Dict[str, Any] = {}
    with zipfile.ZipFile(path, "r") as zf:
        if "docProps/app.xml" not in zf.namelist():
            return out
        with zf.open("docProps/app.xml") as f:
            root = ET.parse(f).getroot()

            out.update({
                "application": _text(root, "Application"),
                "app_version": _text(root, "AppVersion"),
                "company": _text(root, "Company"),
                "manager": _text(root, "Manager"),
                "total_time_minutes": _int(root, "TotalTime"),
                "pages": _int(root, "Pages"),
                "words": _int(root, "Words"),
                "characters": _int(root, "Characters"),
                "characters_with_spaces": _int(root, "CharactersWithSpaces"),
                "lines": _int(root, "Lines"),
                "paragraphs": _int(root, "Paragraphs"),
                "doc_security": _int(root, "DocSecurity"),
                "hyperlinks_changed": _bool(root, "HyperlinksChanged"),
                "links_up_to_date": _bool(root, "LinksUpToDate"),
                "shared_doc": _bool(root, "SharedDoc"),
            })
    return {k: v for k, v in out.items() if v is not None}
