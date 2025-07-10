"""
user_manager.py

Business-logic: login, logout, user CRUD, profile updates, password
changes.  *All* audit-relevant events are logged here – never in the GUI.

© QMToolPyV4 – 2025
"""
from __future__ import annotations

from typing import Optional, Dict

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

        logger.log(
            feature="User",
            event="LoginFailed",
            username=username,
            message="Invalid credentials",
        )
        return None

    def logout(self) -> None:
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
        return self._current_user

    # ------------------------------------------------------------------ #
    # Registration / Creation                                            #
    # ------------------------------------------------------------------ #
    def register_full(self, user_data: Dict) -> bool:
        """
        Create user with optional fields.
        Unknown role strings are mapped to USER.
        """
        creator = self._current_user
        username = user_data.get("username")
        raw_role = user_data.get("role", "USER")

        # Safe role mapping
        role_enum = UserRole.USER
        if isinstance(raw_role, str) and raw_role.upper() in UserRole.__members__:
            role_enum = UserRole[raw_role.upper()]

        if not username or self._repo.get_user(username):
            logger.log(
                feature="User",
                event="CreateFailed",
                user_id=creator.id if creator else None,
                username=creator.username if creator else None,
                message=f"Username '{username}' already exists",
            )
            return False

        ok = self._repo.create_user_full(user_data, role_enum)
        logger.log(
            feature="User",
            event="UserCreated" if ok else "CreateFailed",
            user_id=creator.id if creator else None,
            username=creator.username if creator else None,
            message=f"Created user '{username}'" if ok else "Create failed",
        )
        return ok

    def register_admin_minimal(self, username: str, password: str, email: str) -> bool:
        if self._repo.get_user(username):
            return False
        ok = self._repo.create_admin(username, password, email)
        logger.log(
            feature="User",
            event="UserCreated" if ok else "CreateFailed",
            message=f"Seed-admin '{username}' created" if ok else "Admin seed failed",
        )
        return ok

    # ------------------------------------------------------------------ #
    # Password / Profile                                                 #
    # ------------------------------------------------------------------ #
    def change_password(self, username: str, old_pw: str, new_pw: str) -> bool:
        ok = self._repo.update_password(username, old_pw, new_pw)
        logger.log(
            feature="Password",
            event="Changed" if ok else "ChangeFailed",
            user_id=self._current_user.id if self._current_user else None,
            username=self._current_user.username if self._current_user else username,
            message="Password changed" if ok else "Wrong current password",
        )
        return ok

    def update_user_profile(self, username: str, updates: dict) -> bool:
        ok = self._repo.update_user_fields(username, updates)
        logger.log(
            feature="Profile",
            event="UpdateSuccess" if ok else "UpdateFailed",
            user_id=self._current_user.id if self._current_user else None,
            username=self._current_user.username if self._current_user else username,
            message="Profile updated" if ok else "Profile update failed",
        )
        return ok

    # ------------------------------------------------------------------ #
    # Delete                                                             #
    # ------------------------------------------------------------------ #
    def delete_user(self, username: str) -> bool:
        ok = self._repo.delete_user(username)
        logger.log(
            feature="User",
            event="UserDeleted" if ok else "DeleteFailed",
            user_id=self._current_user.id if self._current_user else None,
            username=self._current_user.username if self._current_user else None,
            message=f"Deleted user '{username}'" if ok else "Delete failed",
        )
        return ok

    # ------------------------------------------------------------------ #
    # Query helpers                                                      #
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
