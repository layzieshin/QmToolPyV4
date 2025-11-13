from __future__ import annotations
from enum import Enum

class SystemRole(str, Enum):
    """System-level roles tied to access rights across the app."""
    ADMIN = "Admin"
    QMB = "QMB"              # Quality Management
    USER = "User"
    VIEWER = "Viewer"
