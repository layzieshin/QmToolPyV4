"""
user_manager.py

Business-Logic:  Login/Logout, User-CRUD, Profil- und Passwort-Änderungen.
*Alle* Audit-Events werden **hier** geloggt – niemals in GUI-Klassen.
"""

from __future__ import annotations

from typing import Optional, Dict

from usermanagement.logic.user_repository import UserRepository
from core.logging.logic.logger import logger
from core.models.user import User, UserRole


class UserManager:
    """Verwaltet Benutzer-Sitzung und -Operationen."""

    # ------------------------------------------------------------------ #
    # Konstruktion                                                       #
    # ------------------------------------------------------------------ #
    def __init__(self) -> None:
        self._repo = UserRepository()
        self._current_user: Optional[User] = None

    # ------------------------------------------------------------------ #
    # Session-Handling                                                   #
    # ------------------------------------------------------------------ #
    def try_login(self, username: str, password: str) -> Optional[User]:
        """
        Prüft Credentials, setzt sowohl
          • self._current_user   (lokal)
          • AppContext.current_user  (global)
        und aktualisiert die Sprache.
        """
        user = self._repo.verify_login(username, password)
        from core.common.app_context import AppContext  # lazy, Kreisfrei
        if user:
            self._current_user = user
            AppContext.current_user = user          # << Sync >>
            AppContext.update_language()

            logger.log(
                feature="User",
                event="LoginSuccess",
                user_id=user.id,
                username=user.username,
                message="Login successful",
            )
            return user

        logger.log(feature="User", event="LoginFailed",
                   username=username, message="Invalid credentials")
        return None

    def logout(self) -> None:
        """
        Loggt Logout *bevor* User gelöscht wird,
        setzt beide User-Referenzen auf None,
        aktualisiert Sprache auf global/default.
        """
        print("logout wurde geklickt")
        from core.common.app_context import AppContext  # lazy

        user = self._current_user or AppContext.current_user
        if user:
            logger.log(feature="User", event="Logout",
                       user_id=user.id, username=user.username,
                       message="User logged out")
        else:
            logger.log(feature="User", event="Logout",
                       user_id=user.id, username=user.username,
                       message="User logged out")
        self._current_user = None
        AppContext.current_user = None          # << Sync >>
        AppContext.update_language()

    def get_logged_in_user(self) -> Optional[User]:
        return self._current_user

    # ------------------------------------------------------------------ #
    # Registrierung / Erstellung                                         #
    # ------------------------------------------------------------------ #
    def register_full(self, user_data: Dict) -> bool:
        creator = self._current_user
        username = user_data.get("username")
        raw_role = user_data.get("role", "USER")

        role_enum = (UserRole[raw_role.upper()]
                     if isinstance(raw_role, str) and raw_role.upper() in UserRole.__members__
                     else UserRole.USER)

        if not username or self._repo.get_user(username):
            logger.log(feature="User", event="CreateFailed",
                       user_id=creator.id if creator else None,
                       username=creator.username if creator else None,
                       message=f"Username '{username}' already exists")
            return False

        ok = self._repo.create_user_full(user_data, role_enum)
        logger.log(feature="User",
                   event="UserCreated" if ok else "CreateFailed",
                   user_id=creator.id if creator else None,
                   username=creator.username if creator else None,
                   message=f"Created user '{username}'" if ok else "Create failed")
        return ok

    def register_admin_minimal(self, username: str,
                               password: str, email: str) -> bool:
        if self._repo.get_user(username):
            return False
        ok = self._repo.create_admin(username, password, email)
        logger.log(feature="User",
                   event="UserCreated" if ok else "CreateFailed",
                   message=f"Seed-admin '{username}' created" if ok else "Admin seed failed")
        return ok

    # ------------------------------------------------------------------ #
    # Passwort / Profil                                                  #
    # ------------------------------------------------------------------ #
    def change_password(self, username: str,
                        old_pw: str, new_pw: str) -> bool:
        ok = self._repo.update_password(username, old_pw, new_pw)
        logger.log(feature="Password",
                   event="Changed" if ok else "ChangeFailed",
                   user_id=self._current_user.id if self._current_user else None,
                   username=self._current_user.username if self._current_user else username,
                   message="Password changed" if ok else "Wrong current password")
        return ok

    def update_user_profile(self, username: str, updates: dict) -> bool:
        ok = self._repo.update_user_fields(username, updates)
        logger.log(feature="Profile",
                   event="UpdateSuccess" if ok else "UpdateFailed",
                   user_id=self._current_user.id if self._current_user else None,
                   username=self._current_user.username if self._current_user else username,
                   message="Profile updated" if ok else "Profile update failed")
        return ok

    # ------------------------------------------------------------------ #
    # Delete                                                             #
    # ------------------------------------------------------------------ #
    def delete_user(self, username: str) -> bool:
        ok = self._repo.delete_user(username)
        logger.log(feature="User",
                   event="UserDeleted" if ok else "DeleteFailed",
                   user_id=self._current_user.id if self._current_user else None,
                   username=self._current_user.username if self._current_user else None,
                   message=f"Deleted user '{username}'" if ok else "Delete failed")
        return ok

    # ------------------------------------------------------------------ #
    # Query-Helper                                                       #
    # ------------------------------------------------------------------ #
    def get_user(self, username: str) -> Optional[User]:
        return self._repo.get_user(username)

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        return self._repo.get_user_by_id(user_id)

    def get_all_users(self) -> list[User]:
        return self._repo.get_all_users()

    def get_editable_fields(self) -> list[str]:
        return [
            "username", "email", "role",
            "full_name", "phone", "department", "job_title",
        ]
