"""
Robust metadata model + normalization utilities for Word/PDF meta extraction.

Changes vs previous version:
- Added 'extended' field to accept callers that pass extended metadata
  (e.g., XMP, DOCX app/extended props, PDF XMP).
- Added 'other' dict to collect any additional, unforeseen sections without
  breaking the constructor.

This module provides:
- DocumentMetadata: a thin container for heterogeneous metadata sections.
- normalize(obj): safely converts any nested structure into JSON-serializable
  primitives without assuming obj is a dataclass.
"""

from __future__ import annotations

from dataclasses import dataclass, field, is_dataclass, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence


# ------------------------ Normalization --------------------------------------
def _is_mapping(obj: Any) -> bool:
    return isinstance(obj, Mapping)


def _is_sequence(obj: Any) -> bool:
    # Exclude str/bytes from "sequence" handling
    return isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray))


def normalize(obj: Any) -> Any:
    """
    Recursively convert arbitrary Python objects into JSON-serializable data.

    Rules:
    - dataclasses: converted via asdict(), then recursively normalized
    - dict-like: keys -> str, values normalized
    - sequences (list/tuple/set): each element normalized, result is list
    - primitives (str/int/float/bool/None): returned as-is
    - datetime/date: ISO-8601 string
    - pathlib.Path: str(path)
    - foreign objects (e.g., python-docx CoreProperties):
        snapshot public, non-callable attributes via dir() and getattr(),
        then normalize that attribute dict. As a last resort, str(obj).
    """
    # Primitives and simple cases
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    if isinstance(obj, Path):
        return str(obj)

    # Dataclass instance
    if is_dataclass(obj):
        try:
            return {k: normalize(v) for k, v in asdict(obj).items()}
        except Exception:
            # Fall back to attribute snapshot if asdict somehow fails
            pass

    # Mapping/dict
    if _is_mapping(obj):
        try:
            return {str(k): normalize(v) for k, v in obj.items()}
        except Exception:
            # As a fallback, turn into str
            return str(obj)

    # Sequence
    if _is_sequence(obj):
        try:
            return [normalize(x) for x in obj]
        except Exception:
            return [str(x) for x in obj]  # last-resort stringification

    # Foreign/opaque objects: attribute snapshot (public, non-callable)
    try:
        attrs: Dict[str, Any] = {}
        for name in dir(obj):
            if name.startswith("_"):
                continue
            try:
                value = getattr(obj, name)
            except Exception:
                continue
            if callable(value):
                continue
            attrs[name] = normalize(value)
        if attrs:
            return attrs
    except Exception:
        pass

    # Final fallback
    try:
        return str(obj)
    except Exception:
        return repr(obj)


# ------------------------ Data Model -----------------------------------------
@dataclass
class DocumentMetadata:
    """
    Container for document metadata sections.

    Fields:
      - core: Core/document properties (title, subject, creator, created, modified, ...)
      - app:  Application properties (application name, pages, words, ...)
      - custom: Custom properties defined by the user
      - file: File-level properties (path, size, timestamps, ...)
      - extended: Additional/extended metadata block (e.g., XMP, DOCX extended/app props)
      - other: Any extra sections not covered above (future-proofing)

    The types are intentionally 'Any' to support heterogeneous upstream objects.
    """
    core: Any = None
    app: Any = None
    custom: Any = None
    file: Any = None
    extended: Any = None
    other: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        Return a normalized, JSON-serializable dict with keys:
        'core', 'app', 'custom', 'file', 'extended', 'other'.
        Each section is independently normalized and may be {} or None.
        """
        return {
            "core": normalize(self.core),
            "app": normalize(self.app),
            "custom": normalize(self.custom),
            "file": normalize(self.file),
            "extended": normalize(self.extended),
            "other": normalize(self.other),
        }

    @classmethod
    def from_sections(cls, **sections: Any) -> "DocumentMetadata":
        """
        Convenience constructor that tolerates various synonyms and collects unknowns.
        Example:
            DocumentMetadata.from_sections(
                core=..., app=..., custom=..., file=..., xmp=..., pdf=..., extended=...
            )
        """
        # Accepted canonical keys
        known_keys = {"core", "app", "custom", "file", "extended"}
        # Map common synonyms to canonical keys
        alias_map = {
            "xmp": "extended",
            "pdf_xmp": "extended",
            "extended_properties": "extended",
            "app_properties": "app",
            "application": "app",
            "docx_app": "app",
            "docx_core": "core",
        }

        payload: Dict[str, Any] = {k: sections.get(k) for k in known_keys}
        other: Dict[str, Any] = {}

        for k, v in sections.items():
            if k in known_keys:
                continue
            target = alias_map.get(k)
            if target:
                if payload.get(target) is None:
                    payload[target] = v
                else:
                    # If both provided, push into 'other' to avoid overwriting
                    other[k] = v
            else:
                other[k] = v

        return cls(
            core=payload.get("core"),
            app=payload.get("app"),
            custom=payload.get("custom"),
            file=payload.get("file"),
            extended=payload.get("extended"),
            other=other,
        )
