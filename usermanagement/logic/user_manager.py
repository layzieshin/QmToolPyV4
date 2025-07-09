# user_manager.py
#
# Handles all user-related business logic.
# - Interfaces between GUI and persistence (user_repository)
# - Manages login state, user registration, profile update, and deletion
# - Provides role logic and validation

from usermanagement.logic.user_repository import UserRepository
from core.models.user import User, UserRole

class UserManager:
    """
    Provides user management functionality including login, registration,
    password management, profile updates, and session tracking.
    """

    def __init__(self):
        """Initializes the manager with a user repository and login session state."""
        self.repo = UserRepository()
        self._current_user = None

    def try_login(self, username: str, password: str) -> User | None:
        """Attempts login. Sets session on success."""
        user = self.repo.verify_login(username, password)
        if user:
            self._current_user = user
        return user

    def logout(self) -> None:
        """Logs out the current user."""
        self._current_user = None

    def get_logged_in_user(self) -> User | None:
        """Returns the currently logged-in user, or None."""
        return self._current_user

    def change_password(self, username: str, old_password: str, new_password: str) -> bool:
        """Validates and sets a new password."""
        return self.repo.update_password(username, old_password, new_password)

    def register_full(self, user_data: dict) -> bool:
        """Registers a user with all available fields."""
        username = user_data.get("username")
        password = user_data.get("password")
        email = user_data.get("email")
        role = user_data.get("role")

        if not username or not password or not email or not role:
            return False

        try:
            role_enum = UserRole[role.upper()]
        except KeyError:
            return False

        if self.repo.get_user(username):
            return False

        return self.repo.create_user_full(user_data, role_enum)

    def register_admin_minimal(self, username: str, password: str, email: str) -> bool:
        """Creates a new admin user with minimal data."""
        if self.repo.get_user(username):
            return False
        self.repo.create_admin(username, password, email)
        return True

    def get_user_by_id(self, user_id: int) -> User | None:
        """Retrieves a user object by ID."""
        return self.repo.get_user_by_id(user_id)

    def get_all_users(self) -> list[User]:
        """Returns all registered users."""
        return self.repo.get_all_users()

    def user_exists(self, username: str) -> bool:
        """Checks whether a user exists."""
        return self.repo.get_user(username) is not None

    def delete_user(self, username: str) -> bool:
        """Deletes a user."""
        return self.repo.delete_user(username)

    def update_user_profile(self, username: str, updates: dict) -> bool:
        """Updates the user profile with the specified fields."""
        return self.repo.update_user_fields(username, updates)

    def get_editable_fields(self) -> list[str]:
        """Returns all user profile fields relevant to GUI forms."""
        return [
            "username", "email", "role", "full_name", "phone", "department", "job_title"
        ]
    def authenticate(self, username: str, password: str):
        return self.try_login(username, password)