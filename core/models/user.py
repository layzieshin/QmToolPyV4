"""
user.py

Defines the central User model and user roles for QMToolPyV2.
All features and modules should use this model for users, permissions, and user-specific data.
This model is designed for maximum extensibility, security, and maintainability.
"""

from enum import Enum
from typing import Optional, List, Dict
from datetime import datetime

class UserRole(Enum):
    """
    Defines all available user roles within the system.
    Extend as needed (e.g., for QM workflows, document lifecycle, external API, etc.).
    """
    USER = "User"
    ADMIN = "Admin"
    QMB = "QMB"
    # Add further roles as needed (e.g., 'Reviewer', 'Approver', 'External', ...)

class User:
    """
    Represents a user with all standard and advanced attributes for QMToolPyV2.
    This model is the single source of truth for all user-related operations, settings, and permissions.
    """

    def __init__(
        self,
        id: int,
        username: str,
        password_hash: str,
        email: str,
        role: UserRole = UserRole.USER,
        full_name: Optional[str] = None,
        is_active: bool = True,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        last_login: Optional[datetime] = None,
        must_change_password: bool = False,
        phone: Optional[str] = None,
        department: Optional[str] = None,
        job_title: Optional[str] = None,
        external_id: Optional[str] = None,
        settings: Optional[Dict] = None,
        extra: Optional[Dict] = None,
        signature_blob: Optional[bytes] = None,
        multi_tenant_id: Optional[int] = None,
        permissions: Optional[List[str]] = None,
    ):
        """
        Initializes a new user instance.

        :param id: Unique integer ID (primary key from database)
        :param username: Unique username or login
        :param password_hash: Secure hashed password
        :param email: User's email address
        :param role: Assigned user role (enum)
        :param full_name: Full name for legal, signature or workflow usage
        :param is_active: Account activation status (logical delete)
        :param created_at: Timestamp of account creation
        :param updated_at: Last modification timestamp
        :param last_login: Last successful login timestamp
        :param must_change_password: Enforces password change on next login
        :param phone: Phone number (optional, for alerts, etc.)
        :param department: User's department/group/OU (for larger orgs)
        :param job_title: Position or job title (optional)
        :param external_id: For mapping to external/legacy/LDAP systems
        :param settings: Arbitrary per-user settings (JSON/dict)
        :param extra: Any further data (free extension dict, e.g. API tokens)
        :param signature_blob: (Optional) Digital signature as binary (e.g. PNG/GIF bytes)
        :param multi_tenant_id: (Optional) Tenant/project/site ID for multi-tenant setups
        :param permissions: (Optional) List of special permission strings
        """
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.email = email
        self.role = role
        self.full_name = full_name
        self.is_active = is_active
        self.created_at = created_at
        self.updated_at = updated_at
        self.last_login = last_login
        self.must_change_password = must_change_password
        self.phone = phone
        self.department = department
        self.job_title = job_title
        self.external_id = external_id
        self.settings = settings or {}
        self.extra = extra or {}
        self.signature_blob = signature_blob
        self.multi_tenant_id = multi_tenant_id
        self.permissions = permissions or []

    def __str__(self):
        """
        Returns a readable summary of the user's core info.
        """
        return (
            f"User({self.id}): {self.username} "
            f"[{self.full_name or 'n/a'}], "
            f"Role: {self.role.value}, "
            f"Email: {self.email}, "
            f"Active: {self.is_active}"
        )

    def has_permission(self, permission: str) -> bool:
        """
        Checks if the user has a specific permission assigned.
        """
        return permission in self.permissions

    # Further helper methods can be added here as needed (e.g., for password, tokens, etc.)

