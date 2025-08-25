"""
auth_bridge.py

Read-only password verification bridge for other modules (e.g., Signature).
This module performs *no* session changes and *no* GUI interaction.
It delegates to UserRepository.verify_login(...) and supports resolving a
username from a user_id or from the current AppContext user as fallback.
"""

from __future__ import annotations

from typing import Optional

from usermanagement.logic.user_repository import UserRepository


def verify_password(*,
                    user_id: Optional[int] = None,
                    username: Optional[str] = None,
                    password: Optional[str] = None) -> bool:
    """
    Verify a password without changing session state.

    Resolution order for username:
        1) explicit 'username' param if provided
        2) resolve by 'user_id' via repository
        3) fallback to AppContext.current_user.username

    :param user_id:    numeric ID of user (optional)
    :param username:   username string (optional)
    :param password:   plaintext password (required)
    :return: True if credentials match, else False
    """
    if not password:
        return False

    repo = UserRepository()

    # 1) explicit username
    uname = username

    # 2) resolve by user_id
    if not uname and user_id is not None:
        try:
            u = repo.get_user_by_id(int(user_id))
            uname = getattr(u, "username", None) if u else None
        except Exception:
            uname = None

    # 3) fallback: current AppContext user
    if not uname:
        try:
            from core.common.app_context import AppContext  # lazy import avoids cycles
            cu = getattr(AppContext, "current_user", None)
            uname = getattr(cu, "username", None) if cu else None
        except Exception:
            uname = None

    if not uname:
        return False

    # Verify against repository (bcrypt)
    try:
        return bool(repo.verify_login(uname, password))
    except Exception:
        return False
