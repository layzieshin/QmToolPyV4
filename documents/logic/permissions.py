"""
Module-local RBAC (Role Based Access Control) for the Documents feature.

Independently maps users to canonical module roles:
  ADMIN, QMB, AUTHOR, EDITOR, REVIEWER, APPROVER, READER

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
    EDITOR = "EDITOR"
    REVIEWER = "REVIEWER"
    APPROVER = "APPROVER"
    READER = "READER"

    ROLE_KEYS = {
        ADMIN: "rbac_admins",
        QMB: "rbac_qmb",
        AUTHOR: "rbac_authors",
        EDITOR: "rbac_editors",
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
        # ===== DEBUG START =====
        print(f"\n--- ModulePermissions.roles_for_user() ---")
        print(f"Input user: {user}")
        # ===== DEBUG END =====

        roles: Set[str] = set()
        if user:
            roles.add(self.READER)  # default

        uid, uname, email = self._user_identifiers(user)
        idset = {s for s in [uid, uname, email] if s}

        # ===== DEBUG START =====
        print(f"Extracted identifiers: uid={uid}, uname={uname}, email={email}")
        # ===== DEBUG END =====

        for role, key in self.ROLE_KEYS.items():
            if role == self.READER:
                # handled above (implicit)
                continue
            members = self._read_members(key)

            # ===== DEBUG START =====
            print(f"Checking role {role} (key={key}): members={members}")
            # ===== DEBUG END =====

            if self._is_member(idset, members):
                roles.add(role)
                # ===== DEBUG START =====
                print(f"  ✓ User IS member of {role}")
                # ===== DEBUG END =====

        # FALLBACK: Check global roles from user object
        if hasattr(user, 'roles'):
            global_roles = getattr(user, 'roles', [])
            # ===== DEBUG START =====
            print(f"Global roles from user. roles: {global_roles}")
            # ===== DEBUG END =====

            if isinstance(global_roles, (list, set, tuple)):
                for r in global_roles:
                    role_name = str(r.name if hasattr(r, 'name') else r).upper()
                    if role_name in ("ADMIN", "QMB", "AUTHOR", "REVIEWER", "APPROVER"):
                        roles.add(role_name)
                        # ===== DEBUG START =====
                        print(f"  ✓ Added global role:  {role_name}")
                        # ===== DEBUG END =====

        if hasattr(user, 'role'):
            global_role = getattr(user, 'role', None)
            if global_role:
                role_name = str(global_role.name if hasattr(global_role, 'name') else global_role).upper()
                if role_name in ("ADMIN", "QMB", "AUTHOR", "REVIEWER", "APPROVER"):
                    roles.add(role_name)
                    # ===== DEBUG START =====
                    print(f"  ✓ Added global role from user.role: {role_name}")
                    # ===== DEBUG END =====

        # ===== DEBUG START =====
        print(f"FINAL ROLES: {roles}")
        print(f"--- End roles_for_user() ---\n")
        # ===== DEBUG END =====

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
