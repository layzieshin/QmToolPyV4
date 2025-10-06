from __future__ import annotations

import zipfile
from datetime import datetime
from typing import List, Optional
import xml.etree.ElementTree as ET

from word_meta.models.review_comment import ReviewComment

# Namespaces
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

def _parse_word_dt(dt: Optional[str]) -> Optional[datetime]:
    """
    Parse typical Word comment datetime (ISO 8601, may include offset or 'Z').
    Returns naive datetime when possible.
    """
    if not dt:
        return None
    s = dt.strip()
    try:
        # Python's fromisoformat doesn't accept 'Z' -> handle manually
        if s.endswith("Z"):
            s = s[:-1]
        return datetime.fromisoformat(s)
    except Exception:
        return None

def _collect_text(elem: ET.Element) -> str:
    """
    Return visible text by concatenating all <w:t> and inserting newlines at <w:p>.
    """
    parts: List[str] = []
    for node in elem.iter():
        if node.tag == f"{W_NS}t" and node.text:
            parts.append(node.text)
        elif node.tag == f"{W_NS}p":
            if parts and not parts[-1].endswith("\n"):
                parts.append("\n")
    text = "".join(parts).strip()
    return text.rstrip("\n")

def read_docx_comments(path: str) -> List[ReviewComment]:
    """
    Read review comments from a .docx (word/comments.xml). Returns [] if none.
    """
    out: List[ReviewComment] = []
    with zipfile.ZipFile(path, "r") as zf:
        if "word/comments.xml" not in zf.namelist():
            return out
        with zf.open("word/comments.xml") as f:
            root = ET.parse(f).getroot()
            for cmt in root.findall(f"{W_NS}comment"):
                try:
                    cid = int(cmt.attrib.get(f"{W_NS}id"))
                except Exception:
                    cid = len(out) + 1
                author = cmt.attrib.get(f"{W_NS}author")
                dt = _parse_word_dt(cmt.attrib.get(f"{W_NS}date"))
                text = _collect_text(cmt)
                if not text:
                    continue
                out.append(ReviewComment(comment_id=cid, author=author or None, date=dt, text=text))
    return out
