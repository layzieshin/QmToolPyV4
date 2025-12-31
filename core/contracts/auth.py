"""core/contracts/auth.py
=====================

Authentication / user-session contracts.

The current code uses a concrete `UserManager` for:
- login/logout
- user CRUD
- profile & password updates
- getting the current logged-in user

This ABC captures the stable cross-feature API.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from core.models.user import User


class IUserManager(ABC):
    """User/session management service."""

    @abstractmethod
    def try_login(self, username: str, password: str) -> Optional[User]:
        """Attempt login and return a User on success."""

    @abstractmethod
    def logout(self) -> None:
        """Logout current user (idempotent)."""

    @abstractmethod
    def get_logged_in_user(self) -> Optional[User]:
        """Return the current logged-in user if any."""

    # --- user administration -------------------------------------------------
    @abstractmethod
    def register_full(self, user_data: Dict[str, Any]) -> bool:
        """Create a new user from a full data dict."""

    @abstractmethod
    def register_admin_minimal(self, username: str, password: str, email: str) -> bool:
        """Create a minimal admin user (bootstrap/seed)."""

    @abstractmethod
    def change_password(self, username: str, old_pw: str, new_pw: str) -> bool:
        """Change password, validating old password."""

    @abstractmethod
    def update_user_profile(self, username: str, updates: Dict[str, Any]) -> bool:
        """Update editable user profile fields."""

    @abstractmethod
    def delete_user(self, username: str) -> bool:
        """Delete a user by username."""

    @abstractmethod
    def get_user(self, username: str) -> Optional[User]:
        """Lookup user by username."""

    @abstractmethod
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Lookup user by id."""

    @abstractmethod
    def get_all_users(self) -> list[User]:
        """Return all users."""

    @abstractmethod
    def get_editable_fields(self) -> list[str]:
        """Return allowed profile fields for editing."""
