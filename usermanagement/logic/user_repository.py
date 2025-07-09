"""
user_repository.py

Low-level SQLite-Zugriff für Benutzer­daten.
– Pfad kommt aus config.ini (ConfigLoader)
– Verzeichnis wird automatisch angelegt
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, Optional

import bcrypt

from core.models.user import User, UserRole
from core.config.config_loader import config_loader


class UserRepository:
    """CRUD-Layer für User-Entitäten."""

    # ------------------------------------------------------------------ #
    # Construction                                                       #
    # ------------------------------------------------------------------ #
    def __init__(self) -> None:
        # Pfad aus config.ini lesen und in Path verwandeln
        raw_path = config_loader.get_config_value("Database", "qm_tool")
        if raw_path is None:
            raise RuntimeError("config.ini: section [Database] key 'qm_tool' missing")

        self.db_path = Path(raw_path)

        # Verzeichnis sicherstellen
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Tabelle anlegen, falls noch nicht vorhanden
        self._ensure_table()

    # ------------------------------------------------------------------ #
    # Public API                                                         #
    # ------------------------------------------------------------------ #
    def get_user(self, username: str) -> Optional[User]:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username.lower(),)
            )
            row = cur.fetchone()
            return self._row_to_user(row) if row else None

    def verify_login(self, username: str, password: str) -> Optional[User]:
        user = self.get_user(username)
        if user and bcrypt.checkpw(password.encode("utf-8"), user.password_hash):
            return user
        return None

    def create_user(self, user_data: dict, role: UserRole = UserRole.USER) -> bool:
        """Legt einen neuen Nutzer an; `user_data` muss username / password / email enthalten."""
        pw_hash = bcrypt.hashpw(user_data["password"].encode(), bcrypt.gensalt())

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
                        user_data["username"].lower(),
                        pw_hash,
                        user_data["email"],
                        role.name,
                        user_data.get("full_name", ""),
                        user_data.get("phone", ""),
                        user_data.get("department", ""),
                        user_data.get("job_title", ""),
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    # -- weitere CRUD-Methoden (update_user_fields, delete_user …) --
    #    … falls benötigt, hier analog anpassen …

    # ------------------------------------------------------------------ #
    # Internals                                                          #
    # ------------------------------------------------------------------ #
    def _connect(self) -> sqlite3.Connection:
        """Öffnet eine SQLite-Verbindung (Path → str)."""
        return sqlite3.connect(str(self.db_path))

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

    # -- Row-Mapper ----------------------------------------------------- #
    @staticmethod
    def _row_to_user(row: tuple | None) -> Optional[User]:
        if row is None:
            return None
        (
            _id,
            username,
            pw_hash,
            email,
            role,
            full_name,
            phone,
            department,
            job_title,
        ) = row
        return User(
            id=_id,
            username=username,
            password_hash=pw_hash,
            email=email,
            role=UserRole[role],
            full_name=full_name or "",
            phone=phone or "",
            department=department or "",
            job_title=job_title or "",
        )
