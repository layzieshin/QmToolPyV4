"""
Helpers for working with Microsoft Word (DOCX):
- create a document from a template
- set core properties (author, title, subject, category, keywords, comments, revision)
- extract core properties and comments (word/comments.xml)

Notes:
- Uses python-docx for core properties (pure Python).
- Comments are parsed from word/comments.xml using zipfile + xml (unabhängig von python-docx).
"""

from __future__ import annotations

# ---- Selftest-Schalter ------------------------------------------------------
SELFTEST: int = 0  # 1 = kurzer Selbsttest beim Direktaufruf (__main__), 0 = aus

import os
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Tuple
from xml.etree import ElementTree as ET

# Optionaler Import (klare Fehlermeldung, falls Paket fehlt, wenn Funktionen genutzt werden)
try:
    from docx import Document  # type: ignore
    _HAVE_DOCX = True
except Exception:
    Document = None  # type: ignore
    _HAVE_DOCX = False


def _ensure_docx_available() -> None:
    if not _HAVE_DOCX:
        raise RuntimeError(
            "python-docx is not installed. Please install it:\n"
            "  pip install python-docx"
        )


def create_from_template(template_path: str, out_path: str, *, props: Dict[str, Any]) -> str:
    """
    Create a new DOCX from the given template and set core properties.
    Returns the path to the written DOCX.
    """
    _ensure_docx_available()
    doc = Document(template_path)  # type: ignore[misc]
    _apply_core_properties(doc, props)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc.save(out_path)
    return out_path


def set_core_properties(docx_path: str, *, props: Dict[str, Any]) -> None:
    _ensure_docx_available()
    doc = Document(docx_path)  # type: ignore[misc]
    _apply_core_properties(doc, props)
    doc.save(docx_path)


def extract_core_and_comments(docx_path: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Returns (core_properties_dict, comments_list).
    comments_list items: {"author": str, "date": datetime|None, "text": str}
    """
    core: Dict[str, Any] = {}
    comments: List[Dict[str, Any]] = []

    # Core via python-docx (wenn vorhanden)
    if _HAVE_DOCX:
        try:
            d = Document(docx_path).core_properties  # type: ignore[misc]
            core = {
                "title": d.title or "",
                "subject": d.subject or "",
                "category": d.category or "",
                "keywords": d.keywords or "",
                "author": d.author or "",
                "last_modified_by": d.last_modified_by or "",
                "comments": d.comments or "",
                "created": d.created if d.created else None,
                "modified": d.modified if d.modified else None,
                "revision": int(d.revision) if d.revision else None,
            }
        except Exception:
            core = {}

    # Kommentare aus word/comments.xml (unabhängig)
    try:
        with zipfile.ZipFile(docx_path) as zf:
            if "word/comments.xml" in zf.namelist():
                xml_bytes = zf.read("word/comments.xml")
                root = ET.fromstring(xml_bytes)
                ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                for c in root.findall("w:comment", ns):
                    author = c.attrib.get(f"{{{ns['w']}}}author", "") or c.attrib.get("author", "")
                    date_str = c.attrib.get(f"{{{ns['w']}}}date", "") or c.attrib.get("date", "")
                    dt = None
                    if date_str:
                        try:
                            # Kommentare speichern ISO8601 / Z
                            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        except Exception:
                            dt = None
                    texts: List[str] = []
                    for t in c.findall(".//w:t", ns):
                        texts.append(t.text or "")
                    comments.append({"author": author, "date": dt, "text": "".join(texts).strip()})
    except Exception:
        # best-effort: kein harter Fehler, wenn ZIP/Comments fehlen
        pass

    return core, comments


def _apply_core_properties(doc: Any, props: Dict[str, Any]) -> None:
    """
    Applies common core properties to a python-docx Document.
    `doc` ist Any, damit Typchecker nicht python-docx verlangt.
    """
    cp = doc.core_properties
    if "title" in props: cp.title = str(props["title"])
    if "subject" in props: cp.subject = str(props["subject"])
    if "category" in props: cp.category = str(props["category"])
    if "keywords" in props: cp.keywords = str(props["keywords"])
    if "author" in props: cp.author = str(props["author"])
    if "last_modified_by" in props: cp.last_modified_by = str(props["last_modified_by"])
    if "comments" in props: cp.comments = str(props["comments"])
    if "revision" in props and props["revision"] is not None:
        try:
            cp.revision = int(props["revision"])
        except Exception:
            pass


# ---- kleiner Selbsttest -----------------------------------------------------
if __name__ == "__main__" and SELFTEST:
    import tempfile
    print("[word_tools] SELFTEST running...")
    tmp = tempfile.mkdtemp()
    tpl = os.path.join(tmp, "tpl.docx")
    out = os.path.join(tmp, "out.docx")

    # 1) einfache Vorlage erzeugen
    _ensure_docx_available()
    d = Document()  # type: ignore[misc]
    d.add_paragraph("Hello, world.")
    d.save(tpl)

    # 2) Dokument aus Vorlage erzeugen
    create_from_template(tpl, out, props={"author": "u1", "title": "Demo", "revision": 3})

    # 3) künstliches comments.xml einfügen (ein Kommentar)
    xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:comment w:id="0" w:author="Max Mustermann" w:date="2023-01-02T03:04:05Z">
    <w:p><w:r><w:t>Das ist ein Kommentar.</w:t></w:r></w:p>
  </w:comment>
</w:comments>
"""
    with zipfile.ZipFile(out, "a") as zf:
        zf.writestr("word/comments.xml", xml)

    # 4) Auslesen
    core, comments = extract_core_and_comments(out)
    print("CORE:", core)
    print("COMMENTS:", comments)
    print("[word_tools] SELFTEST done.")
