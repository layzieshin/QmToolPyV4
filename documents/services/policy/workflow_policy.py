"""Workflow policy service (no IO).

TODO: Implement workflow transition validation based on in-memory policy data.
"""
from __future__ import annotations

from typing import Iterable, List

from documents.dto.type_spec import TypeSpec
from documents.enum.document_status import DocumentStatus


class WorkflowPolicy:
    """Policy evaluation for workflow transitions."""

    def __init__(self, *, type_spec: TypeSpec) -> None:
        self._type_spec = type_spec

    def allowed_transitions(self, status: DocumentStatus) -> List[str]:
        """Return allowed action identifiers from the given status.

        TODO: Read from policy configuration.
        """
        _ = status
        return []

    def next_status(self, *, action_id: str, status: DocumentStatus) -> DocumentStatus:
        """Resolve the next status for a given action.

        TODO: Implement policy-driven mapping.
        """
        raise NotImplementedError("Workflow policy not implemented")

    def requires_signature(self, action_id: str) -> bool:
        """Determine whether signatures are required for the action.

        TODO: Use type-specific requirements.
        """
        _ = action_id
        return False

    def requires_reason(self, action_id: str) -> bool:
        """Determine whether a reason is required for the action.

        TODO: Configure per action in policy.
        """
        _ = action_id
        return False
