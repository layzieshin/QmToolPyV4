"""documents/services/policy/signature_policy.py
=================================================

Signature policy (no IO).

The documents feature only depends on an interface for signature handling.
This policy determines *which* module roles must provide signatures for a given
document type and action.
"""
from __future__ import annotations

from typing import List

from documents.dto.document_type_spec import DocumentTypeSpec
from documents.enum.document_action import DocumentAction


class SignaturePolicy:
    """Evaluate signature requirements per type/action."""

    def required_roles(self, *, type_spec: DocumentTypeSpec, action_id: str) -> List[str]:
        """Return module role ids that must sign for the action."""
        action = DocumentAction(action_id)

        # Default rule: signatures are required on publish if configured for the type.
        if action is DocumentAction.PUBLISH:
            return list(type_spec.signature_roles())

        return []
