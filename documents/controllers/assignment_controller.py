"""AssignmentController - handles role assignments per document."""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple

from documents.logic.repository import DocumentsRepository
from documents.dto.assignments import Assignments

try:
    from documents.logic.rbac_service import RBACService
except Exception:
    RBACService = None  # type: ignore


class AssignmentController:
    """
    Manages role assignments per document.

    Responsibilities:
    - Get assignees
    - Set assignees
    - Validate assignments
    - Get available users

    SRP: Assignment logic only, no workflow. 
    """

    def __init__(
            self,
            *,
            repository: DocumentsRepository,
            rbac_service: Optional[RBACService] = None
    ) -> None:
        """
        Args: 
            repository: Documents repository
            rbac_service: Optional RBAC service for user list
        """
        self._repo = repository
        self._rbac = rbac_service

    def get_assignees(self, doc_id: str) -> Dict[str, List[str]]:
        """
        Get current assignments. 

        Args:
            doc_id: Document ID

        Returns:
            Dict with keys: "AUTHOR", "REVIEWER", "APPROVER" (uppercase)
        """
        raw = self._repo.get_assignees(doc_id)

        # Normalize keys to uppercase
        return {
            "AUTHOR": raw.get("AUTHOR", []) or raw.get("authors", []),
            "REVIEWER": raw.get("REVIEWER", []) or raw.get("reviewers", []),
            "APPROVER": raw.get("APPROVER", []) or raw.get("approvers", []),
        }

    def set_assignees(
            self,
            doc_id: str,
            assignments: Assignments
    ) -> Tuple[bool, Optional[str]]:
        """
        Save assignments. 

        Args:
            doc_id: Document ID
            assignments: Assignments DTO

        Returns: 
            (success: bool, error_msg: Optional[str])
        """
        # Validate first
        valid, error_msg = self.validate_assignments(assignments)
        if not valid:
            return False, error_msg

        try:
            mapping = {
                "AUTHOR": assignments.authors,
                "REVIEWER": assignments.reviewers,
                "APPROVER": assignments.approvers,
            }
            self._repo.set_assignees(doc_id, mapping)
            return True, None
        except Exception as ex:
            return False, f"Zuweisungsfehler: {ex}"

    def validate_assignments(
            self,
            assignments: Assignments
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate assignments (business rules).

        Rules:
        - At least 1 approver required
        - Reviewer ≠ Approver (Separation of Duties)

        Args:
            assignments:  Assignments to validate

        Returns: 
            (valid: bool, error_msg: Optional[str])
        """
        # At least 1 approver
        if not assignments.approvers:
            return False, "Mindestens ein Freigeber erforderlich."

        # Reviewer ≠ Approver
        reviewers_set = set(assignments.reviewers or [])
        approvers_set = set(assignments.approvers or [])

        if reviewers_set & approvers_set:
            overlap = reviewers_set & approvers_set
            return False, f"Prüfer und Freigeber dürfen nicht identisch sein: {', '.join(overlap)}"

        return True, None

    def get_available_users(self) -> List[Dict[str, str]]:
        """
        Get available users for assignment dialog.

        Returns:
            List of user dicts (id, username, email, full_name)
        """
        if not self._rbac:
            return []

        try:
            return self._rbac.list_users()
        except Exception:
            return []