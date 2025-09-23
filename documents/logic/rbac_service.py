"""
RBACService – centralizes membership maintenance (Settings) and role requests (DB).

- Membership lists are stored in SettingsManager as comma-separated usernames/ids/emails.
- Role requests are stored in the documents sqlite database table "rbac_requests".
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional, Sequence

from core.common.app_context import AppContext
from core.settings.logic.settings_manager import SettingsManager

# Try to import your repository as in your codebase; fall back to local file if needed.
try:
    from usermanagement.logic.user_repository import UserRepository
except Exception:
    from user_repository import UserRepository  # type: ignore


@dataclass(frozen=True)
class RoleRequest:
    req_id: int
    requested_by: str       # user id (string)
    username: str
    roles: tuple[str, ...]
    comment: str | None
    status: str             # PENDING | APPROVED | DENIED
    requested_at: datetime
    processed_by: str | None = None
    processed_at: datetime | None = None


class RBACService:
    FEATURE_ID = "documents"

    def __init__(self, db_path: str, sm: SettingsManager) -> None:
        self._db_path = db_path
        self._sm = sm
        self._users = UserRepository()
        self._ensure_schema()

    # ---- DB schema -----------------------------------------------------------
    def _ensure_schema(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rbac_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    requested_by TEXT NOT NULL,
                    username TEXT NOT NULL,
                    roles TEXT NOT NULL,
                    comment TEXT,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    requested_at TEXT NOT NULL,
                    processed_by TEXT,
                    processed_at TEXT
                )
            """)
            conn.commit()

    # ---- Users ---------------------------------------------------------------
    def list_users(self) -> list[dict]:
        """
        Returns a lightweight list of users from your global user repository.
        """
        users = self._users.get_all_users()  # type: ignore[attr-defined]
        out = []
        for u in users:
            out.append({
                "id": str(getattr(u, "id")),
                "username": getattr(u, "username", ""),
                "email": getattr(u, "email", ""),
                "full_name": getattr(u, "full_name", "") or "",
            })
        return out

    # ---- Membership (Settings) ----------------------------------------------
    def get_members(self, role_key: str) -> list[str]:
        raw = str(self._sm.get(self.FEATURE_ID, role_key, "") or "")
        parts = [p.strip() for p in raw.replace(";", ",").split(",")]
        return [p for p in parts if p]

    def set_members(self, role_key: str, identifiers: Iterable[str]) -> None:
        vals = ",".join(sorted({str(x).strip() for x in identifiers if str(x).strip()}))
        self._sm.set(self.FEATURE_ID, role_key, vals)

    # ---- Requests ------------------------------------------------------------
    def submit_request(self, roles: Sequence[str], comment: str | None) -> int:
        user = getattr(AppContext, "current_user", None)
        uid = str(getattr(user, "id", "")) if user else ""
        username = getattr(user, "username", "") if user else ""
        if not uid or not username:
            raise RuntimeError("Not logged in")

        roles_str = ",".join(sorted({r.upper() for r in roles if r}))
        now = datetime.utcnow().isoformat(timespec="seconds")
        with sqlite3.connect(self._db_path) as conn:
            cur = conn.execute("""
                INSERT INTO rbac_requests(requested_by,username,roles,comment,status,requested_at)
                VALUES (?,?,?,?, 'PENDING', ?)
            """, (uid, username, roles_str, comment, now))
            conn.commit()
            return int(cur.lastrowid)

    def list_requests(self, status: Optional[str] = None) -> list[RoleRequest]:
        sql = "SELECT * FROM rbac_requests"
        args: list = []
        if status:
            sql += " WHERE status=?"
            args.append(status.upper())
        sql += " ORDER BY requested_at DESC"
        out: list[RoleRequest] = []
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, tuple(args)).fetchall()
            for r in rows:
                out.append(RoleRequest(
                    req_id=int(r["id"]),
                    requested_by=str(r["requested_by"]),
                    username=str(r["username"]),
                    roles=tuple(str(r["roles"]).split(",")),
                    comment=str(r["comment"]) if r["comment"] else None,
                    status=str(r["status"]),
                    requested_at=datetime.fromisoformat(str(r["requested_at"])),
                    processed_by=str(r["processed_by"]) if r["processed_by"] else None,
                    processed_at=datetime.fromisoformat(str(r["processed_at"])) if r["processed_at"] else None,
                ))
        return out

    def approve_request(self, req_id: int) -> None:
        req = self._get(req_id)
        # apply: add user (by username OR id) to each role list
        for role in req.roles:
            key = _role_to_key(role)
            current = set(self.get_members(key))
            current.add(req.username)  # store username (works fine & human-readable)
            self.set_members(key, current)
        self._set_status(req_id, "APPROVED")

    def deny_request(self, req_id: int) -> None:
        self._set_status(req_id, "DENIED")

    # ---- Internals -----------------------------------------------------------
    def _get(self, req_id: int) -> RoleRequest:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            r = conn.execute("SELECT * FROM rbac_requests WHERE id=?", (req_id,)).fetchone()
            if not r:
                raise KeyError("Request not found")
            return RoleRequest(
                req_id=int(r["id"]),
                requested_by=str(r["requested_by"]),
                username=str(r["username"]),
                roles=tuple(str(r["roles"]).split(",")),
                comment=str(r["comment"]) if r["comment"] else None,
                status=str(r["status"]),
                requested_at=datetime.fromisoformat(str(r["requested_at"])),
                processed_by=str(r["processed_by"]) if r["processed_by"] else None,
                processed_at=datetime.fromisoformat(str(r["processed_at"])) if r["processed_at"] else None,
            )

    def _set_status(self, req_id: int, new_status: str) -> None:
        user = getattr(AppContext, "current_user", None)
        uid = str(getattr(user, "id", "")) if user else ""
        now = datetime.utcnow().isoformat(timespec="seconds")
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                UPDATE rbac_requests SET status=?, processed_by=?, processed_at=? WHERE id=?
            """, (new_status.upper(), uid or None, now, req_id))
            conn.commit()


def _role_to_key(role: str) -> str:
    r = role.upper()
    if r == "ADMIN": return "rbac_admins"
    if r == "QMB": return "rbac_qmb"
    if r == "AUTHOR": return "rbac_authors"
    if r == "REVIEWER": return "rbac_reviewers"
    if r == "APPROVER": return "rbac_approvers"
    if r == "READER": return "rbac_readers"
    raise KeyError(f"Unknown role: {role}")
