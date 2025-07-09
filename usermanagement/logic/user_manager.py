"""
user_manager.py

Business-logic for user handling: login, logout, registration, profile
updates, password changes.  All audit-relevant events are logged here
(never in the GUI layer).

© QMToolPyV4 – 2025
"""
from __future__ import annotations

from typing import Optional

from usermanagement.logic.user_repository import UserRepository
from core.logging.logic.logger import logger
from core.models.user import User, UserRole


class UserManager:
    """Provides user-management functionality and session tracking."""

    # ------------------------------------------------------------------ #
    # Construction                                                       #
    # ------------------------------------------------------------------ #
    def __init__(self) -> None:
        self._repo = UserRepository()
        self._current_user: Optional[User] = None

    # ------------------------------------------------------------------ #
    # Session handling                                                   #
    # ------------------------------------------------------------------ #
    def try_login(self, username: str, password: str) -> Optional[User]:
        """
        Attempt to authenticate *username* with *password*.

        On success:
            • sets `_current_user`
            • logs "LoginSuccess"
        On failure:
            • logs "LoginFailed"
        """
        user = self._repo.verify_login(username, password)
        if user:
            self._current_user = user
            logger.log(
                feature="User",
                event="LoginSuccess",
                user_id=user.id,
                username=user.username,
                message="Login successful",
            )
            return user

        # Failed attempt
        logger.log(
            feature="User",
            event="LoginFailed",
            username=username,
            message="Invalid credentials",
        )
        return None

    def logout(self) -> None:
        """Log out the current user and write audit log."""
        if self._current_user:
            logger.log(
                feature="User",
                event="Logout",
                user_id=self._current_user.id,
                username=self._current_user.username,
                message="User logged out",
            )
        self._current_user = None

    def get_logged_in_user(self) -> Optional[User]:
        """Return the currently logged-in user (or None)."""
        return self._current_user

    # ------------------------------------------------------------------ #
    # CRUD / helpers (unchanged)                                         #
    # ------------------------------------------------------------------ #
    def change_password(self, username: str, old_pw: str, new_pw: str) -> bool:
        return self._repo.update_password(username, old_pw, new_pw)

    def register_full(self, user_data: dict) -> bool:
        username = user_data.get("username")
        if not username or self._repo.get_user(username):
            return False
        role_enum = UserRole[user_data.get("role", "USER").upper()]
        return self._repo.create_user_full(user_data, role_enum)

    def register_admin_minimal(self, username: str, password: str, email: str) -> bool:
        if self._repo.get_user(username):
            return False
        self._repo.create_admin(username, password, email)
        return True

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        return self._repo.get_user_by_id(user_id)

    def get_all_users(self) -> list[User]:
        return self._repo.get_all_users()

    def delete_user(self, username: str) -> bool:
        return self._repo.delete_user(username)

    def update_user_profile(self, username: str, updates: dict) -> bool:
        return self._repo.update_user_fields(username, updates)

    def get_editable_fields(self) -> list[str]:
        return [
            "username", "email", "role",
            "full_name", "phone", "department", "job_title",
        ]
