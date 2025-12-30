"""
user_repository.py

Low-level SQLite access for user data.  All CRUD helpers required by
UserManager are exposed here.

Database path comes from config.ini  →  section [Database] key "qm_tool".
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, Optional

import bcrypt

from core.models.user import User, UserRole
from core.config.config_loader import config_loader
from core.logging.logic.logger import logger      #  ← NEU
from core.common.db_interface import DatabaseAccess, create_sqlite_connection


class UserRepository(DatabaseAccess):
    """Complete CRUD layer for `User` entities."""

    # ------------------------------------------------------------------ #
    # Construction                                                       #
    # ------------------------------------------------------------------ #
    def __init__(self) -> None:
        self._db_path = config_loader.get_qm_db_path()
        self._ensure_table()

    # ------------------------------------------------------------------ #
    # Query helpers                                                      #
    # ------------------------------------------------------------------ #
    def get_user(self, username: str) -> Optional[User]:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username.lower(),)
            )
            row = cur.fetchone()
            return self._row_to_user(row) if row else None

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        with self._connect() as conn:
            cur = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            return self._row_to_user(cur.fetchone())

    def get_all_users(self) -> List[User]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM users ORDER BY LOWER(username)"
            ).fetchall()
            return [self._row_to_user(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Authentication / Password                                          #
    # ------------------------------------------------------------------ #
    def verify_login(self, username: str, password: str) -> Optional[User]:
        user = self.get_user(username)
        if user and bcrypt.checkpw(password.encode(), user.password_hash):
            return user
        return None

    def update_password(self, username: str, old_pw: str, new_pw: str) -> bool:
        """Change password after verifying the old one."""
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT id, password_hash FROM users WHERE username = ?",
                (username.lower(),),
            )
            row = cur.fetchone()
            if not row or not bcrypt.checkpw(old_pw.encode(), row["password_hash"]):
                return False

            new_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt())
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (new_hash, row["id"]),
            )
            return True

    # ------------------------------------------------------------------ #
    # Create                                                             #
    # ------------------------------------------------------------------ #
    def create_user_full(self, data: dict, role: UserRole) -> bool:
        """
        Insert a fully-populated user row.
        Expected keys: username, password, email, role, full_name, phone,
                       department, job_title
        """
        pw_hash = bcrypt.hashpw(data["password"].encode(), bcrypt.gensalt())
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO users
                      (username, password_hash, email, role,
                       full_name, phone, department, job_title)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        data["username"].lower(),
                        pw_hash,
                        data["email"],
                        role.name,
                        data.get("full_name", ""),
                        data.get("phone", ""),
                        data.get("department", ""),
                        data.get("job_title", ""),
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def create_user(self, data: dict, role: UserRole = UserRole.USER) -> bool:
        """Alias für create_user_full – akzeptiert Minimal-Dict."""
        return self.create_user_full(data, role)

    def create_admin(self, username: str, password: str, email: str) -> bool:
        return self.create_user_full(
            {
                "username": username,
                "password": password,
                "email": email,
            },
            role=UserRole.ADMIN,
        )

    # ------------------------------------------------------------------ #
    # Update selective fields                                            #
    # ------------------------------------------------------------------ #
    def update_user_fields(self, username: str, updates: dict) -> bool:
        if not updates:
            return True

        allowed = {
            "email", "role", "full_name",
            "phone", "department", "job_title",
        }
        updates = {k: v for k, v in updates.items() if k in allowed}
        if not updates:
            return False

        set_clause = ", ".join(f"{k}=?" for k in updates)
        params = list(updates.values()) + [username.lower()]

        with self._connect() as conn:
            cur = conn.execute(
                f"UPDATE users SET {set_clause} WHERE LOWER(username) = ?", params
            )
            return cur.rowcount == 1

    # ------------------------------------------------------------------ #
    # Delete                                                             #
    # ------------------------------------------------------------------ #
    def delete_user(self, username: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM users WHERE LOWER(username) = ?", (username.lower(),)
            )
            return cur.rowcount == 1

    # ------------------------------------------------------------------ #
    # Internals                                                          #
    # ------------------------------------------------------------------ #
    def _connect(self) -> sqlite3.Connection:
        return self.connect()

    @property
    def db_path(self) -> Path:
        return self._db_path

    def connect(self) -> sqlite3.Connection:
        return create_sqlite_connection(self._db_path)

    def _ensure_table(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash BLOB NOT NULL,
                    email TEXT NOT NULL,
                    role TEXT NOT NULL,
                    full_name TEXT,
                    phone TEXT,
                    department TEXT,
                    job_title TEXT
                )
                """
            )
            conn.commit()

    # ------------------------------------------------------------------ #
    # Row-mapper                                                         #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _row_to_user(row: sqlite3.Row | tuple | None) -> Optional[User]:
        if row is None:
            return None

        (
            _id, username, pw_hash, email, role,
            full_name, phone, department, job_title,
        ) = row

        # -------- NEW: unknown roles fall back to USER -------------------
        try:
            role_enum = UserRole[role]
        except KeyError:
            role_enum = UserRole.USER
            # optional: kleine Warnung ins Log
            logger.log(
                feature="User",
                event="UnknownRole",
                message=f"Unknown role '{role}' mapped to USER (username='{username}')",
            )
        # ----------------------------------------------------------------

        return User(
            id=_id,
            username=username,
            password_hash=pw_hash,
            email=email,
            role=role_enum,
            full_name=full_name or "",
            phone=phone or "",
            department=department or "",
            job_title=job_title or "",
        )
