"""
locale.py

Centralized language management for UI texts (i18n).

Usage
-----
from core.i18n.locale import locale
Label(self, text=locale.t("login"))
"""

from __future__ import annotations

from core.logging.logic.logger import logger
from core.common.app_context import AppContext

LOCALE_TRACK_MISSING_KEYS = True   # set False in production


class LocaleManager:
    """Singleton-style helper that stores translations and current language."""

    # ------------------------------------------------------------------ #
    # Construction                                                       #
    # ------------------------------------------------------------------ #
    def __init__(self, default_lang: str = "en") -> None:
        self.supported = {
            "en": self._en_dict(),
            "de": self._de_dict(),
            # add further languages here
        }
        self.lang = default_lang
        self._missing_keys_logged: set[str] = set()

    # ------------------------------------------------------------------ #
    # Public API                                                         #
    # ------------------------------------------------------------------ #
    def set_language(self, lang: str) -> None:
        if lang in self.supported:
            self.lang = lang

    def t(self, key: str) -> str:
        """
        Return localized string.  If the key is missing and tracking is
        enabled, write a log entry and return the key itself.
        """
        value = self.supported.get(self.lang, {}).get(key)
        if value is not None:
            return value

        if LOCALE_TRACK_MISSING_KEYS and key not in self._missing_keys_logged:
            user = AppContext.current_user
            logger.log(
                feature="Locale",
                event="MissingKey",
                user_id=user.id if user else None,
                username=user.username if user else None,
                message=f"Missing translation key '{key}' (lang={self.lang})",
            )
            self._missing_keys_logged.add(key)

        return key

    # ------------------------------------------------------------------ #
    # Internal dictionaries                                              #
    # ------------------------------------------------------------------ #
    def _en_dict(self) -> dict[str, str]:
        return {
            "role": "Role",
            "job_title": "Job Title",
            "department": "Department",
            "phone": "Phone",
            "full_name": "Full Name",
            "feature_name": "Feature Name",
            "feature_description": "Feature Description",
            "feature_enabled": "Feature Enabled",
            "feature_disabled": "Feature Disabled",
            "feature_created": "Feature Created",
            "feature_updated": "Feature Updated",
            "feature_deleted": "Feature Deleted",
            "feature_not_found": "Feature not found",
            "feature_already_exists": "Feature already exists",
            "feature_list": "Feature List",
            "feature_add": "Add Feature",
            "feature_edit": "Edit Feature",
            "feature_delete": "Delete Feature",
            "feature_save": "Save Feature",
            "feature_cancel": "Cancel",
            "feature_name_required": "Feature name is required.",
            "feature_description_required": "Feature description is required.",
            "add": "Add",
            "login": "Login",
            "logout": "Logout",
            "username": "Username",
            "password": "Password",
            "fullname": "Full Name",
            "email": "Email",
            "settings": "Settings",
            "save": "Save",
            "cancel": "Cancel",
            "language": "Language",
            "select_language": "Select Language",
            "feature": "Feature",
            "documents": "Documents",
            "sign_pdf": "Sign PDF",
            "user_management": "User Management",
            "admin": "Admin",
            "welcome": "Welcome",
            "error": "Error",
            "success": "Success",
            # Profile / settings
            "profile_title": "Profile",
            "save_profile": "Save Profile",
            "profile_updated": "Profile Updated",
            "profile_saved": "Profile changes have been saved.",
            "update_failed": "Update Failed",
            "profile_save_failed": "Failed to save profile changes.",
            "name_email_required": "Full name and email must not be empty.",
            # Password
            "change_password": "Change Password",
            "current_password": "Current password",
            "new_password": "New password",
            "repeat_new_password": "Repeat new password",
            "change_password_btn": "Change Password",
            "all_fields_required": "All fields are required.",
            "passwords_no_match": "New passwords do not match.",
            "password_changed": "Password changed successfully.",
            "current_password_wrong": "Current password is incorrect.",
            # Language
            "language_settings": "Language Settings",
            "set_language_btn": "Set Language",
            "language_changed": "Language changed",
            "restart_needed": "Please restart the application for the language change to take full effect.",
            # Tabs
            "profile_tab": "Profile & Account",
            "edit": "Edit",
            "delete": "Delete",
            "log_view": "Log View",
        }

    def _de_dict(self) -> dict[str, str]:
        return {
            "role": "Rolle",
            "job_title": "Funktion",
            "department": "Abteilung",
            "phone": "Telefon",
            "full_name": "Vollständiger Name",
            "feature_name": "Feature Name",
            "feature_description": "Feature Beschreibung",
            "feature_enabled": "Feature Aktiviert",
            "feature_disabled": "Feature Deaktiviert",
            "feature_created": "Feature Erstellt",
            "feature_updated": "Feature Aktualisiert",
            "feature_deleted": "Feature Gelöscht",
            "feature_not_found": "Feature nicht gefunden",
            "feature_already_exists": "Feature existiert bereits",
            "feature_list": "Feature Liste",
            "feature_add": "Feature hinzufügen",
            "feature_edit": "Feature bearbeiten",
            "feature_delete": "Feature löschen",
            "feature_save": "Feature speichern",
            "feature_cancel": "Feature abbrechen",
            "feature_name_required": "Feature Name ist erforderlich.",
            "feature_description_required": "Feature description ist erforderlich.",
            "add": "Neu",
            "login": "Anmelden",
            "logout": "Abmelden",
            "username": "Benutzername",
            "password": "Passwort",
            "fullname": "Vollständiger Name",
            "email": "E-Mail",
            "settings": "Einstellungen",
            "save": "Speichern",
            "cancel": "Abbrechen",
            "language": "Sprache",
            "select_language": "Sprache auswählen",
            "feature": "Funktion",
            "documents": "Dokumente",
            "sign_pdf": "PDF signieren",
            "user_management": "Benutzerverwaltung",
            "admin": "Administrator",
            "welcome": "Willkommen",
            "error": "Fehler",
            "success": "Erfolg",
            # Profile / settings
            "profile_title": "Profil",
            "save_profile": "Profil speichern",
            "profile_updated": "Profil aktualisiert",
            "profile_saved": "Profiländerungen wurden gespeichert.",
            "update_failed": "Aktualisierung fehlgeschlagen",
            "profile_save_failed": "Profiländerungen konnten nicht gespeichert werden.",
            "name_email_required": "Name und E-Mail dürfen nicht leer sein.",
            # Password
            "change_password": "Passwort ändern",
            "current_password": "Aktuelles Passwort",
            "new_password": "Neues Passwort",
            "repeat_new_password": "Neues Passwort wiederholen",
            "change_password_btn": "Passwort ändern",
            "all_fields_required": "Alle Felder sind erforderlich.",
            "passwords_no_match": "Neue Passwörter stimmen nicht überein.",
            "password_changed": "Passwort erfolgreich geändert.",
            "current_password_wrong": "Das aktuelle Passwort ist nicht korrekt.",
            # Language
            "language_settings": "Spracheinstellungen",
            "set_language_btn": "Sprache setzen",
            "language_changed": "Sprache geändert",
            "restart_needed": "Bitte starten Sie die Anwendung neu, damit die Sprachänderung wirksam wird.",
            # Tabs
            "profile_tab": "Profil & Konto",
            "edit": "Bearbeiten",
            "delete": "Löschen",
            "log_view": "Logbuch",
        }


# Singleton instance
locale = LocaleManager()
