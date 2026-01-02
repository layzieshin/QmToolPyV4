"""Document type registry (no IO).

Loads and provides document type specifications.
"""

from __future__ import annotations
from typing import Dict, Optional
from pathlib import Path
import json

from documents.dto.type_spec import TypeSpec


class TypeRegistry:
    """Registry for document type specifications."""

    def __init__(self):
        self._types: Dict[str, TypeSpec] = {}

    @classmethod
    def load_from_directory(cls, directory: str | Path) -> "TypeRegistry":
        """
        Load type registry from documents_document_types.json.

        Args:
            directory: Directory containing policy files

        Returns:
            TypeRegistry instance
        """
        registry = cls()

        base = Path(directory)
        types_file = base / "documents_document_types.json"

        if not types_file.exists():
            return registry

        try:
            with types_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return registry

        # Load document types
        doc_types = data.get("document_types", {})

        for code, config in doc_types.items():
            if not isinstance(config, dict):
                continue

            spec = TypeSpec(
                code=str(code),
                label=config.get("label", code),
                requires_review=bool(config.get("requires_review", True)),
                allow_self_approval=bool(config.get("allow_self_approval", False)),
                required_signatures=config.get("required_signatures", []),
                metadata=config
            )

            registry.register(spec)

        return registry

    def register(self, spec: TypeSpec) -> None:
        """
        Register a document type specification.

        Args:
            spec: TypeSpec instance
        """
        self._types[spec.code] = spec

    def get(self, code: str) -> Optional[TypeSpec]:
        """
        Retrieve a type specification.

        Args:
            code: Document type code

        Returns:
            TypeSpec or None if not found
        """
        return self._types.get(code)

    def exists(self, code: str) -> bool:
        """Check if type exists."""
        return code in self._types

    def list_all(self) -> Dict[str, TypeSpec]:
        """Get all registered types."""
        return dict(self._types)