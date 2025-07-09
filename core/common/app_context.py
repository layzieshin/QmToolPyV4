"""
app_context.py

Runtime-Singletons für QMToolPy:
• shared LogController
• shared UserManager
• aktuell eingeloggter Benutzer (current_user)

Andere Module importieren einfach `AppContext`.
"""

from __future__ import annotations

from core.logging.logic.log_controller import LogController
from usermanagement.logic.user_manager import UserManager

class AppContext:
    """Globale Laufzeit-Instanzen und Login-Status."""
    log_controller = LogController()
    user_manager = UserManager()
    current_user = None          # type: core.models.user.User | None
