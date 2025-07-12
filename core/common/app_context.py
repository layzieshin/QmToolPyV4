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
from core.settings.logic.settings_manager import SettingsManager
from core.i18n.locale import locale   # bereits vorhanden

class AppContext:
    """Central runtime context (no GUI-state)."""

    # ------------------------------------------------------------------ #
    # Shared singletons                                                  #
    # ------------------------------------------------------------------ #
    log_controller = LogController()
    user_manager = UserManager()
    settings_manager = SettingsManager()
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

        # settings
        "settings_manager": settings_manager,
    }

    @classmethod
    def register_service(cls, name: str, instance: object) -> None:
        """
        Dynamically add a service to the registry.
        Call this from plugins if they provide their own singletons.
        """
        cls.services[name] = instance
    @classmethod
    def update_language(cls) -> None:
        """Load language (user override > global > 'de')."""
        # 1) versuchen, user-spezifisch
        lang = cls.settings_manager.get("app", "language",
                                        user_specific=True, default=None)
        # 2) fallback global
        if lang is None:
            lang = cls.settings_manager.get("app", "language",
                                            user_specific=False, default="de")

        from core.i18n.locale import locale   # lazy
        locale.set_language(lang)

AppContext.update_language()