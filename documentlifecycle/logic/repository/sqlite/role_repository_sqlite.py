"""
===============================================================================
RoleRepositorySQLite – per-document role assignments
-------------------------------------------------------------------------------
Purpose:
    Manage per-document role assignments (Author/Reviewer/Approver) using
    the 'document_roles' table. Multiple assignments per role are supported.

Design:
    - Idempotent set_assignments() replaces all assignments for a document.
    - list_users_for_role() returns user ids for fast policy checks.
===============================================================================
"""
from __future__ import annotations
from typing import List

from .base_sqlite_repo import BaseSQLiteRepo
from documentlifecycle.models.role_assignment import RoleAssignment
from documentlifecycle.models.workflow_role import WorkflowRole


class RoleRepositorySQLite(BaseSQLiteRepo):
    """
    SQLite implementation of RoleRepository (assignments CRUD subset).

    Methods
    -------
    list_assignments(document_id) -> list[RoleAssignment]
        Return all role assignments for a document.
    list_users_for_role(document_id, role) -> list[int]
        Return only user ids for quick policy checks.
    set_assignments(document_id, assignments) -> None
        Replace all assignments for the document transactionally.
    """

    def list_assignments(self, document_id: int) -> List[RoleAssignment]:
        """Fetch all role assignments for the given document."""
        cur = self.conn.execute(
            "SELECT document_id, user_id, role, note FROM document_roles WHERE document_id=?",
            (document_id,)
        )
        rows = cur.fetchall()
        return [
            RoleAssignment(document_id=int(r["document_id"]), user_id=int(r["user_id"]),
                           role=WorkflowRole(r["role"]), note=r["note"])
            for r in rows
        ]

    def list_users_for_role(self, document_id: int, role: WorkflowRole) -> List[int]:
        """Return only the user ids for a given role on a document."""
        cur = self.conn.execute(
            "SELECT user_id FROM document_roles WHERE document_id=? AND role=?",
            (document_id, role.value)
        )
        return [int(r[0]) for r in cur.fetchall()]

    def set_assignments(self, document_id: int, assignments: List[RoleAssignment]) -> None:
        """
        Replace all role assignments for the document in a single transaction.

        This approach keeps the DB consistent and avoids partial updates.
        """
        with self.conn:
            self.conn.execute("DELETE FROM document_roles WHERE document_id=?", (document_id,))
            for a in assignments:
                self.conn.execute(
                    "INSERT INTO document_roles(document_id, user_id, role, note) VALUES (?,?,?,?)",
                    (a.document_id, a.user_id, a.role.value, a.note)
                )
