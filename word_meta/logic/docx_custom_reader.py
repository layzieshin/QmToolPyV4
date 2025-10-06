from __future__ import annotations

import zipfile
from datetime import datetime
from typing import Any, Dict, List
import xml.etree.ElementTree as ET

from word_meta.models.custom_property import CustomProperty

# Namespaces
CP_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/custom-properties}"
VT_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes}"

def _parse_vt(elem: ET.Element) -> (str, Any):
    """
    Parse a <vt:*> element into (value_type, python_value).
    """
    tag = elem.tag.replace(VT_NS, "")
    text = (elem.text or "").strip()

    if tag == "lpwstr":
        return tag, text
    if tag in ("i1", "i2", "i4", "i8"):
        try:
            return tag, int(text)
        except Exception:
            return tag, text
    if tag in ("r4", "r8", "decimal"):
        try:
            return tag, float(text)
        except Exception:
            return tag, text
    if tag == "bool":
        return tag, text.lower() in ("true", "1")
    if tag == "filetime":
        # Usually ISO-like; keep as ISO string if parseable
        try:
            return tag, datetime.fromisoformat(text).isoformat()
        except Exception:
            return tag, text
    # Arrays and other compound types -> flatten to string
    return tag, text

def read_docx_custom_properties(path: str) -> List[CustomProperty]:
    """
    Read docProps/custom.xml (custom document properties).
    Returns a list of CustomProperty.
    """
    out: List[CustomProperty] = []
    with zipfile.ZipFile(path, "r") as zf:
        if "docProps/custom.xml" not in zf.namelist():
            return out
        with zf.open("docProps/custom.xml") as f:
            root = ET.parse(f).getroot()
            for prop in root.findall(f"{CP_NS}property"):
                name = prop.attrib.get("name", "")
                pid = prop.attrib.get("pid")
                try:
                    pid_int = int(pid) if pid is not None else None
                except Exception:
                    pid_int = None

                # one child vt:* holding the value
                vt_child = next((c for c in prop if c.tag.startswith(VT_NS)), None)
                if vt_child is None:
                    continue
                val_type, val = _parse_vt(vt_child)
                out.append(CustomProperty(name=name, value_type=val_type, value=val, pid=pid_int))
    return out
