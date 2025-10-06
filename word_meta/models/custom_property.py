from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Optional

@dataclass(frozen=True)
class CustomProperty:
    """
    Model for a single custom document property from docProps/custom.xml.
    value_type is the VT-element name (e.g., 'lpwstr', 'i4', 'r8', 'bool', 'filetime').
    """
    name: str
    value_type: str
    value: Any
    pid: Optional[int] = None
