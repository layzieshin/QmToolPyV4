"""Documents feature exceptions.

TODO: Add richer domain error types.
"""
from __future__ import annotations


class DocumentsError(Exception):
    """Base exception for documents feature."""


class PolicyViolationError(DocumentsError):
    """Raised when a policy rule is violated."""
