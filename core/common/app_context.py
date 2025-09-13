"""
core/common/app_context.py
==========================

Globaler Runtime-Kontext & Service-Registry für QMToolPy.
"""

from __future__ import annotations

from pathlib import Path

from core.config.config_loader import LABELS_TSV_PATH, MODULES_JSON_PATH
from core.i18n.translation_manager import translations
from core.logging.logic.log_controller import LogController
from core.settings.logic.settings_manager import settings_manager  # Instanz!
from usermanagement.logic.user_manager import UserManager
from core.common.signature_api import SignatureAPI  # NEW

# ------------------------------------------------------------------ #
#  Übersetzungsdatei einmalig laden                                  #
# ------------------------------------------------------------------ #
root = Path(__file__).resolve().parents[2]
labels_file = LABELS_TSV_PATH

label_files = [labels_file]
label_files += list(root.glob("**/label.tsv"))

if label_files:
    translations.load_files(label_files)
else:
    translations.translations = {"de": {}, "en": {}}

# ------------------------------------------------------------------ #
#  Zentraler Context                                                 #
# ------------------------------------------------------------------ #
class AppContext:
    """Central runtime context (no GUI-state)."""

    # ---------- Singleton-Instanzen -----------------------------------
    log_controller = LogController()
    user_manager = UserManager()
    settings_manager = settings_manager         # ← KEIN Aufruf mehr!

    current_user = None                         # type: ignore[assignment]

    # ---------- Service-Registry für Auto-Injection -------------------
    services: dict[str, object] = {
        "log_controller":   log_controller,
        "controller":       log_controller,     # Alias
        "user_manager":     user_manager,
        "settings_manager": settings_manager,
    }

    # ---------- Dynamische Registrierung ------------------------------
    @classmethod
    def register_service(cls, name: str, instance: object) -> None:
        cls.services[name] = instance

    # ---------- Sprache nach Login / Wechsel aktualisieren ------------
    @classmethod
    def update_language(cls) -> None:
        """
        Ermittelt aktuelle Sprache:
        1) user-spezifisch  2) global  3) Fallback 'de'
        """
        lang = cls.settings_manager.get("app", "language",
                                        user_specific=True, fallback=None)
        if lang is None:
            lang = cls.settings_manager.get("app", "language",
                                            fallback="de")
        from core.i18n.locale import locale  # lazy import
        locale.set_language(lang)


# ------------------------------------------------------------------ #
#  Kürzel für Übersetzungen                                          #
# ------------------------------------------------------------------ #
def T(label: str) -> str:
    lang = AppContext.settings_manager.get("app", "language",
                                           user_specific=True, fallback="de")
    return translations.t(label, lang)


# Initiale Sprache setzen
AppContext.update_language()
# Attach global signature API for all modules
AppContext.signature = SignatureAPI()  # type: ignore[attr-defined]
