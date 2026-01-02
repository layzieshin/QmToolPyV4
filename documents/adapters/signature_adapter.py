"""Signature adapter abstraction.

TODO: Integrate with external signature providers.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class SignatureAdapter(ABC):
    """Abstract signature adapter for workflow steps."""

    @abstractmethod
    def sign(self, *, doc_id: str, payload: bytes) -> bytes:
        """Return signature artifact bytes."""
        raise NotImplementedError
