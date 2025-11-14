"""
===============================================================================
Role Repository Protocol – per-document role assignments
-------------------------------------------------------------------------------
Purpose:
    Abstract read/write access to per-document role assignments (Author,
    Reviewer, Approver, ...). Multiple assignments per role are allowed.

Design:
    - Read methods are used by policies to check phase permissions.
    - Write methods will be used by the role editor (later milestone).
===============================================================================
"""
from __future__ import annotations
from typing import Protocol, List

from documentlifecycle.models.role_assignment import RoleAssignment
from documentlifecycle.models.workflow_role import WorkflowRole


class RoleRepository(Protocol):
    """
    Contract for per-document role assignments.

    Methods
    -------
    list_assignments(document_id) -> list[RoleAssignment]
        Return all assignments across roles for a document.
    list_users_for_role(document_id, role) -> list[int]
        Return user ids assigned to the given role for the document.
    set_assignments(document_id, assignments) -> None
        Replace all assignments for the document (idempotent update).
    """

    def list_assignments(self, document_id: int) -> List[RoleAssignment]:
        ...

    def list_users_for_role(self, document_id: int, role: WorkflowRole) -> List[int]:
        ...

    def set_assignments(self, document_id: int, assignments: List[RoleAssignment]) -> None:
        ...
