"""documents/dto/document_type_spec.py
=================================

Document type specification (settings-driven).

Document types are treated as *data*, not code logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from documents.enum.module_role import ModuleRole


@dataclass(frozen=True, slots=True)
class DocumentTypeSpec:
    """Immutable definition of a document type and its workflow requirements."""

    code: str
    requires_review: bool
    requires_approval: bool
    allow_self_approval: bool
    required_signatures: Tuple[str, ...]  # ModuleRole ids

    @staticmethod
    def from_mapping(code: str, data: dict) -> "DocumentTypeSpec":
        """Create a spec from a mapping (e.g. settings JSON)."""
        required = tuple(str(x) for x in (data.get("required_signatures") or ()))
        return DocumentTypeSpec(
            code=code,
            requires_review=bool(data.get("requires_review")),
            requires_approval=bool(data.get("requires_approval")),
            allow_self_approval=bool(data.get("allow_self_approval")),
            required_signatures=required,
        )

    def signature_roles(self) -> Tuple[str, ...]:
        """Return normalized module role ids required to sign."""
        normalized = []
        for role in self.required_signatures:
            r = str(role).upper()
            if r == ModuleRole.APPROVER.value:
                r = ModuleRole.FREIGEBER.value
            normalized.append(r)
        return tuple(normalized)
