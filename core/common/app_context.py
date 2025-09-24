# core/common/app_context.py
"""
Global runtime context & service registry for QMToolPy.
"""

from __future__ import annotations

from pathlib import Path

from core.config.config_loader import LABELS_TSV_PATH, MODULES_JSON_PATH
from core.i18n.translation_manager import translations
from core.logging.logic.log_controller import LogController
from core.settings.logic.settings_manager import settings_manager  # instance
from usermanagement.logic.user_manager import UserManager

# ------------------------------------------------------------------ #
#  Load translation file once                                        #
# ------------------------------------------------------------------ #
root = Path(__file__).resolve().parents[2]

# Central dictionary (e.g. translations/labels.tsv)
central_file = Path(LABELS_TSV_PATH) if LABELS_TSV_PATH else None

# Gather module dictionaries:
# - prefer plural 'labels.tsv'
# - also support legacy singular 'label.tsv'
module_candidates = list(root.glob("**/labels.tsv"))
module_candidates += list(root.glob("**/label.tsv"))  # backward-compat

# Build final, existing, de-duplicated file list (central first)
seen: set[Path] = set()
label_files: list[Path] = []

def _add(p: Path | None) -> None:
    if not p:
        return
    try:
        rp = p.resolve()
    except Exception:
        return
    if rp.exists() and rp not in seen:
        seen.add(rp)
        label_files.append(rp)

_add(central_file)
for p in module_candidates:
    _add(p)

if label_files:
    translations.load_files(label_files)  # merges multiple TSVs. :contentReference[oaicite:1]{index=1}
else:
    # empty init to avoid KeyErrors later
    translations.translations = {"de": {}, "en": {}}

# ------------------------------------------------------------------ #
#  Central AppContext                                                #
# ------------------------------------------------------------------ #
class AppContext:
    """Central runtime context (no GUI state)."""

    # ---------- Singleton instances -----------------------------------
    log_controller = LogController()
    user_manager = UserManager()
    settings_manager = settings_manager  # keep instance reference

    current_user = None  # type: ignore[assignment]

    # ---------- Service registry for DI -------------------------------
    services: dict[str, object] = {
        "log_controller": log_controller,
        "controller": log_controller,  # alias
        "user_manager": user_manager,
        "settings_manager": settings_manager,
    }

    # ---------- Dynamic registration ---------------------------------
    @classmethod
    def register_service(cls, name: str, instance: object) -> None:
        cls.services[name] = instance

    # ---------- Language refresh on login / change --------------------
    @classmethod
    def update_language(cls) -> None:
        """
        Determine active language:
        1) user-specific  2) global  3) fallback 'de'
        """
        lang = cls.settings_manager.get("app", "language", user_specific=True, fallback=None)
        if lang is None:
            lang = cls.settings_manager.get("app", "language", fallback="de")
        from core.i18n.locale import locale  # lazy import
        locale.set_language(lang)

    # ---------- Lazy accessor: Signature API (avoids cycles) ----------
    _signature_api_singleton = None  # type: ignore[var-annotated]

    @staticmethod
    def signature():
        """
        Lazy accessor for the SignatureAPI.
        Avoids import cycles by importing inside the method.
        """
        if AppContext._signature_api_singleton is None:
            from core.common.signature_api import SignatureAPI  # lazy import
            AppContext._signature_api_singleton = SignatureAPI()
        return AppContext._signature_api_singleton


# ------------------------------------------------------------------ #
#  Translation shortcut                                              #
# ------------------------------------------------------------------ #
def T(label: str) -> str:
    lang = AppContext.settings_manager.get("app", "language", user_specific=True, fallback="de")
    return translations.t(label, lang)  # logs missing keys once. :contentReference[oaicite:2]{index=2}


# Initial language
AppContext.update_language()

# Make translation available on the context (used by APIs via ctx.T/ctx.translate)
AppContext.T = staticmethod(T)           # type: ignore[attr-defined]
AppContext.translate = AppContext.T      # type: ignore[attr-defined]

# IMPORTANT:
# Do NOT instantiate SignatureAPI at module import time.
# Use: AppContext.signature()  # when needed
