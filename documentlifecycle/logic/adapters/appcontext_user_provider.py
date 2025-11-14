"""
===============================================================================
AppContext User Provider – bridge from host AppContext to policy CurrentUser
-------------------------------------------------------------------------------
Purpose:
    Read the active user from the host application's AppContext and convert it
    into a policy-facing 'CurrentUser' (system roles + start-workflow flag).

Robustness:
    - Works even if AppContext or certain user fields are missing.
    - Maps roles from either enum-like objects or strings; also respects
      boolean hints (is_admin/is_qmb) or a 'roles' collection if present.

Contract:
    - get_current_user() -> CurrentUser

Notes:
    - Admin/QMB are always allowed to start workflows. Otherwise we check an
      optional boolean 'can_start_workflow' on the host user object.
===============================================================================
"""
from __future__ import annotations
from typing import Set

from documentlifecycle.logic.policy.permission_policy import CurrentUser
from documentlifecycle.models.system_role import SystemRole

try:
    from core.common.app_context import AppContext  # type: ignore
except Exception:  # pragma: no cover
    AppContext = None  # type: ignore

try:
    from core.models.user import UserRole  # type: ignore
except Exception:  # pragma: no cover
    UserRole = None  # type: ignore


class AppContextUserProvider:
    """Adapter reading the current user from the host's AppContext."""

    def get_current_user(self) -> CurrentUser:
        """Return current user mapped to policy roles and start flag."""
        if AppContext is None or not hasattr(AppContext, "current_user"):
            return CurrentUser(id=0, system_roles={SystemRole.VIEWER}, can_start_workflow=False)

        u = getattr(AppContext, "current_user", None)
        if u is None:
            return CurrentUser(id=0, system_roles={SystemRole.VIEWER}, can_start_workflow=False)

        uid = getattr(u, "id", 0) or 0
        roles: Set[SystemRole] = self._map_roles(u)
        can_start = (
            SystemRole.ADMIN in roles
            or SystemRole.QMB in roles
            or bool(getattr(u, "can_start_workflow", False))
        )
        return CurrentUser(id=uid, system_roles=roles, can_start_workflow=can_start)

    # ---------------------------- internals ---------------------------- #
    def _map_roles(self, u) -> Set[SystemRole]:
        """Resolve the host user's system roles with best-effort mapping."""
        roles: Set[SystemRole] = set()
        raw = getattr(u, "role", None)

        if raw is not None and UserRole is not None:
            try:
                name = raw.name if hasattr(raw, "name") else str(raw)
                roles.add(self._map_name_to_system_role(str(name).upper()))
                return roles
            except Exception:
                pass

        if isinstance(raw, str):
            roles.add(self._map_name_to_system_role(raw.upper()))
        else:
            if bool(getattr(u, "is_admin", False)):
                roles.add(SystemRole.ADMIN)
            if bool(getattr(u, "is_qmb", False)):
                roles.add(SystemRole.QMB)

            many = getattr(u, "roles", None)
            if isinstance(many, (list, tuple, set)):
                for item in many:
                    try:
                        name = item.name if hasattr(item, "name") else str(item)
                        roles.add(self._map_name_to_system_role(str(name).upper()))
                    except Exception:
                        pass

        if not roles:
            roles.add(SystemRole.USER)
        return roles

    @staticmethod
    def _map_name_to_system_role(name: str) -> SystemRole:
        """Map relaxed role names from the host to SystemRole."""
        if name in {"ADMIN", "SYSTEMADMIN", "SYSADMIN"}:
            return SystemRole.ADMIN
        if name in {"QMB", "QUALITY", "QUALITYMANAGER", "QM"}:
            return SystemRole.QMB
        if name in {"VIEWER", "READONLY", "READ_ONLY"}:
            return SystemRole.VIEWER
        return SystemRole.USER
