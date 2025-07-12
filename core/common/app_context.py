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

from pathlib import Path

from core.i18n.translation_manager import translations
root = Path(__file__).resolve().parents[2]      # Projekt-Stamm finden
labels_file = root / "translations" / "labels.tsv"

if labels_file.exists():
    translations.load_file(labels_file)
else:
    # Notfall: leere Tabelle anlegen, damit die App trotzdem startet
    translations.translations = {"de": {}, "en": {}}

from core.logging.logic.log_controller import LogController
from usermanagement.logic.user_manager import UserManager
from core.settings.logic.settings_manager import SettingsManager


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

def T(label: str) -> str:
    # Hier aus Settings lesen:
    lang = AppContext.settings_manager.get("app", "language", user_specific=True, default="de")
    return translations.t(label, lang)

AppContext.update_language()