"""core/contracts/workflow.py
=========================

Workflow / lifecycle contracts.

The repo contains workflow logic in `documentlifecycle`. This contract allows
other features (e.g., documents) to respond to workflow transitions without
importing concrete implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class IWorkflowEngine(ABC):
    """Workflow engine for documents."""

    @abstractmethod
    def get_status(self, document_id: str) -> Optional[str]:
        """Return workflow status for a document."""

    @abstractmethod
    def set_status(self, document_id: str, new_status: str, *, actor_id: str | None = None) -> None:
        """Set workflow status for a document."""

    @abstractmethod
    def can_transition(self, document_id: str, target_status: str, *, actor_id: str | None = None) -> bool:
        """Return True if a transition is allowed."""
