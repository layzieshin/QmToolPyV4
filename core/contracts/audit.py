"""core/contracts/audit.py
======================

Audit trail contracts.

The codebase currently logs events via `core.logging.logic.logger.logger`.
This interface is introduced to make audit sinks replaceable (file, DB, remote),
while keeping a single place where audit semantics are defined.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping, Optional


class IAuditLogger(ABC):
    """Write-only audit trail logger."""

    @abstractmethod
    def log(
        self,
        feature: str,
        event: str,
        *,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        message: str = "",
        data: Mapping[str, Any] | None = None,
    ) -> None:
        """Write an audit event."""
