"""
===============================================================================
code_parser – parse document code and title from filenames
-------------------------------------------------------------------------------
Expected filename scheme: "CODE_Title.ext"

CODE:
  - Standard:  X##TT###     (X = area letter, ## = 2 digits, TT = 2 letters
                              for type, ### = 3 digits)
               Examples:  B01VA001, A02AA007, C03LS041, D99AM012, E11PR003
  - EXT (extern): may appear as 'EX...' (we map EX -> EXT)
  - XO  (external order form): XO...
  - QMH special: "QMH##"     (e.g. QMH01_Qualitätsmanagementhandbuch)

Title:
  - Text after the first underscore, without extension.

If parsing fails, we return (code=None, title=stem, type_code=None).
===============================================================================
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

_STD_CODE_RE = re.compile(r"^([A-Za-z])(\d{2})([A-Za-z]{2})(\d{3})$")  # TT = 2 letters
_QMH_RE = re.compile(r"^(QMH)(\d{2})$", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedCode:
    area_letter: str | None
    procedure: str | None
    type_code_2: str | None     # always two letters (EX mapped later to EXT)
    sequence: str | None
    code: str
    title: str


def _split_name(name: str) -> tuple[str, str] | None:
    """Split at the first underscore into (code, title)."""
    if "_" not in name:
        return None
    code, title = name.split("_", 1)
    return code, title


def parse_code_and_title_from_basename(basename: str) -> Optional[ParsedCode]:
    """
    Try to parse "CODE_Title" where CODE matches one of the patterns above.
    Returns ParsedCode or None.
    """
    name = basename.rsplit(".", 1)[0] if "." in basename else basename
    parts = _split_name(name)
    if not parts:
        return None
    code_part, title = parts

    # QMH special: "QMH##"
    m_qmh = _QMH_RE.match(code_part)
    if m_qmh:
        qmh, num = m_qmh.groups()
        return ParsedCode(
            area_letter=None,
            procedure=num,
            type_code_2="QM",  # we will map "QM" -> QMH in enum mapping
            sequence=None,
            code=f"{qmh.upper()}{num}",
            title=title,
        )

    # Standard: X##TT###
    m_std = _STD_CODE_RE.match(code_part)
    if m_std:
        area, proc, tt2, seq = m_std.groups()
        return ParsedCode(
            area_letter=area,
            procedure=proc,
            type_code_2=tt2.upper(),
            sequence=seq,
            code=code_part,
            title=title,
        )

    return None


def parse_code_and_title_from_path(path: str | Path) -> Tuple[Optional[str], str, Optional[str]]:
    """
    Convenience: return (code, title, type_code_2letters).
    If pattern does not match, code=None, title=stem, type_code_2=None.
    """
    p = Path(path)
    parsed = parse_code_and_title_from_basename(p.name)
    if parsed:
        return parsed.code, parsed.title, parsed.type_code_2
    return None, p.stem, None
