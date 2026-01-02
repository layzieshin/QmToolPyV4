"""Document type registry (no IO).

TODO: Load type specs from settings/config in application layer.
"""
from __future__ import annotations

from typing import Dict

from documents.dto.type_spec import TypeSpec


class TypeRegistry:
    """Registry for document type specifications."""

    def __init__(self) -> None:
        self._types: Dict[str, TypeSpec] = {}

    def register(self, spec: TypeSpec) -> None:
        """Register a document type specification."""
        self._types[spec.code] = spec

    def get(self, code: str) -> TypeSpec:
        """Retrieve a type specification.

        TODO: Provide error handling for missing types.
        """
        return self._types[code]
