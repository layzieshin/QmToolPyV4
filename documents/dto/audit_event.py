"""Audit event DTO.

TODO: Add actor identifiers, payload details, and signature references.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass(frozen=True)
class AuditEvent:
    """Immutable audit log event."""

    event_type: str
    occurred_at: datetime
    actor_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
