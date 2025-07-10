"""
app_context.py

Global runtime singletons & service-registry for QMToolPy.

• log_controller  – shared LogController instance
• user_manager    – shared UserManager instance
• current_user    – who is logged-in right now (or None)

`services` is the single source of truth for dependency injection:
  key   … the exact parameter name a view expects
  value … the instance that should be injected
"""

from __future__ import annotations

from core.logging.logic.log_controller import LogController
from usermanagement.logic.user_manager import UserManager


class AppContext:
    """Central runtime context (no GUI-state)."""

    # ------------------------------------------------------------------ #
    # Shared singletons                                                  #
    # ------------------------------------------------------------------ #
    log_controller = LogController()
    user_manager = UserManager()

    # Session information (updated in UserManager / MainWindow)
    current_user = None                # type: core.models.user.User | None

    # ------------------------------------------------------------------ #
    # Service-Registry for auto-injection                                #
    # ------------------------------------------------------------------ #
    # Map constructor-parameter names → singleton instances
    services: dict[str, object] = {
        # logging
        "log_controller": log_controller,
        "controller":      log_controller,   # common alias

        # user management / auth
        "user_manager":    user_manager,
    }

    @classmethod
    def register_service(cls, name: str, instance: object) -> None:
        """
        Dynamically add a service to the registry.
        Call this from plugins if they provide their own singletons.
        """
        cls.services[name] = instance
