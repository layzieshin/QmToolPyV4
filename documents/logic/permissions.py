"""
Module-local RBAC (Role Based Access Control) for the Documents feature.

Independently maps users to canonical module roles:
  ADMIN, QMB, AUTHOR, REVIEWER, APPROVER, READER

Membership is configured via SettingsManager under the "documents" feature
and can be maintained via a user-picker dialog in settings (see settings_view).
Role requests are stored in the module's sqlite database.

Important:
- Every logged-in user implicitly has READER.
- Additional roles come from settings membership.
"""

from __future__ import annotations

from typing import Iterable, Set, Tuple, Optional


class ModulePermissions:
    FEATURE_ID = "documents"

    ADMIN = "ADMIN"
    QMB = "QMB"
    AUTHOR = "AUTHOR"
    REVIEWER = "REVIEWER"
    APPROVER = "APPROVER"
    READER = "READER"

    ROLE_KEYS = {
        ADMIN: "rbac_admins",
        QMB: "rbac_qmb",
        AUTHOR: "rbac_authors",
        REVIEWER: "rbac_reviewers",
        APPROVER: "rbac_approvers",
        READER: "rbac_readers",
    }

    def __init__(self, settings_manager) -> None:
        self._sm = settings_manager

    # ------- Public API -------------------------------------------------------
    def roles_for_user(self, user: object | None) -> Set[str]:
        """
        Resolve the set of module roles for the given user based on settings.
        Every logged-in user is at least READER.
        """
        roles: Set[str] = set()
        if user:
            roles.add(self.READER)  # default

        uid, uname, email = self._user_identifiers(user)
        idset = {s for s in [uid, uname, email] if s}

        for role, key in self.ROLE_KEYS.items():
            if role == self.READER:
                # handled above (implicit)
                continue
            members = self._read_members(key)
            if self._is_member(idset, members):
                roles.add(role)

        return roles

    def has_any(self, user: object | None, required: Iterable[str]) -> bool:
        user_roles = self.roles_for_user(user)
        req = {r.upper() for r in required}
        return bool(user_roles & req)

    # ------- Internals --------------------------------------------------------
    def _read_members(self, key: str) -> Tuple[str, ...]:
        raw = str(self._sm.get(self.FEATURE_ID, key, "") or "")
        parts = [p.strip() for p in raw.replace(";", ",").split(",")]
        items = tuple(p for p in parts if p)
        return items

    @staticmethod
    def _user_identifiers(user: object | None) -> tuple[Optional[str], Optional[str], Optional[str]]:
        if not user:
            return None, None, None
        uid = None
        uname = None
        email = None
        for attr in ("id", "user_id", "uid"):
            val = getattr(user, attr, None)
            if isinstance(val, (str, int)):
                uid = str(val)
                break
        for attr in ("username", "name", "login"):
            val = getattr(user, attr, None)
            if isinstance(val, str) and val.strip():
                uname = val.strip()
                break
        for attr in ("email", "mail"):
            val = getattr(user, attr, None)
            if isinstance(val, str) and val.strip():
                email = val.strip()
                break
        return uid, uname, email

    @staticmethod
    def _is_member(idset: Set[str], members: Tuple[str, ...]) -> bool:
        if not members:
            return False
        ids_norm = {s.lower() for s in idset}
        mem_norm = [m.strip().lower() for m in members]
        return any((m in ids_norm) for m in mem_norm)
