"""Signature policy service (no IO).

TODO: Evaluate required signatures per document type and action.
"""
from __future__ import annotations

from typing import List


class SignaturePolicy:
    """Signature requirements for workflow steps."""

    def required_roles(self, *, doc_type: str, action_id: str) -> List[str]:
        """Return module roles required to sign.

        TODO: Implement configuration-driven requirements.
        """
        _ = doc_type
        _ = action_id
        return []
