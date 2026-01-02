"""documents/services/document_type_registry.py
=================================================

Settings-driven registry for document type specs (no UI, minimal IO via settings_manager).

The registry reads a mapping from settings under the namespace ``documents`` and key
``document_types``. If settings are missing, defaults are used.

This module is intentionally small and deterministic to keep it easy to test.
"""
from __future__ import annotations

from typing import Dict, Mapping

from core.contracts.settings import ISettingsManager
from documents.dto.document_type_spec import DocumentTypeSpec
from documents.enum.module_role import ModuleRole


DEFAULT_DOCUMENT_TYPES: Dict[str, Dict] = {
    # Strict types
    "VA": {
        "requires_review": True,
        "requires_approval": True,
        "allow_self_approval": False,
        "required_signatures": [ModuleRole.EDITOR.value, ModuleRole.REVIEWER.value, ModuleRole.FREIGEBER.value],
    },
    "QMH": {
        "requires_review": True,
        "requires_approval": True,
        "allow_self_approval": False,
        "required_signatures": [ModuleRole.EDITOR.value, ModuleRole.REVIEWER.value, ModuleRole.FREIGEBER.value],
    },
    # Simple types
    "AA": {"requires_review": False, "requires_approval": False, "allow_self_approval": False, "required_signatures": []},
    "LS": {"requires_review": False, "requires_approval": False, "allow_self_approval": False, "required_signatures": []},
    "OD": {"requires_review": False, "requires_approval": False, "allow_self_approval": False, "required_signatures": []},
    "MM": {"requires_review": False, "requires_approval": False, "allow_self_approval": False, "required_signatures": []},
    # Special cases
    "FB": {"requires_review": False, "requires_approval": True, "allow_self_approval": True, "required_signatures": []},
    "extAA": {"requires_review": False, "requires_approval": False, "allow_self_approval": False, "required_signatures": []},
}


class IDocumentTypeRegistry:
    """Interface for retrieving document type specifications."""

    def get(self, code: str) -> DocumentTypeSpec:  # pragma: no cover - ABC-like
        raise NotImplementedError


class DocumentTypeRegistry(IDocumentTypeRegistry):
    """Load and serve :class:`DocumentTypeSpec` objects from settings."""

    SETTINGS_NAMESPACE = "documents"
    SETTINGS_KEY = "document_types"

    def __init__(self, *, settings_manager: ISettingsManager) -> None:
        self._settings_manager = settings_manager
        self._cache: Dict[str, DocumentTypeSpec] | None = None

    def reload(self) -> None:
        """Drop cache so next access loads from settings."""
        self._cache = None

    def _load(self) -> Dict[str, DocumentTypeSpec]:
        raw = self._settings_manager.get(
            self.SETTINGS_NAMESPACE,
            self.SETTINGS_KEY,
            fallback=DEFAULT_DOCUMENT_TYPES,
            user_specific=False,
        )
        if not isinstance(raw, Mapping):
            raw = DEFAULT_DOCUMENT_TYPES

        result: Dict[str, DocumentTypeSpec] = {}
        for code, data in dict(raw).items():
            if not isinstance(code, str) or not isinstance(data, Mapping):
                continue
            spec = DocumentTypeSpec.from_mapping(code, dict(data))
            result[spec.code] = spec

        # Ensure defaults exist even if settings omit them.
        for code, data in DEFAULT_DOCUMENT_TYPES.items():
            if code not in result:
                result[code] = DocumentTypeSpec.from_mapping(code, data)

        return result

    def get(self, code: str) -> DocumentTypeSpec:
        """Return the spec for a type code.

        Raises:
            KeyError: if the type code is unknown.
        """
        if self._cache is None:
            self._cache = self._load()
        key = str(code)
        return self._cache[key]
