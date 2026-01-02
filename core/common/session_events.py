"""
core/common/session_events.py

Defines event objects for user session changes.

The session is owned by AppContext. Other components can subscribe to these events
to react to login/logout without direct coupling.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional

from core.models.user import User


SessionEventType = Literal["login", "logout", "user_changed"]


@dataclass(frozen=True, slots=True)
class UserSessionEvent:
    """Represents a user session change event."""

    type: SessionEventType
    old_user: Optional[User]
    new_user: Optional[User]
    reason: str
    ts_utc: datetime
