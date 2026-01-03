"""AssignmentController - handles role assignments per document."""

from __future__ import annotations
from typing import Callable, Dict, List, Optional, Tuple
import logging

from documents.dto.assignments import Assignments

logger = logging.getLogger(__name__)


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
            repository,
            rbac_service=None,
            user_provider:  Optional[Callable[[], List[Dict[str, str]]]] = None
    ) -> None:
        """
        Args:
            repository: Documents repository
            rbac_service:  Optional RBAC service for user list
            user_provider: Optional callable that returns list of user dicts
        """
        self._repo = repository
        self._rbac = rbac_service
        self._user_provider = user_provider

    def get_assignees(self, doc_id: str) -> Dict[str, List[str]]:
        """
        Get current assignments.

        Args:
            doc_id: Document ID

        Returns:
            Dict with keys: "AUTHOR", "REVIEWER", "APPROVER" (uppercase)
        """
        try:
            raw = self._repo.get_assignees(doc_id)

            return {
                "AUTHOR": raw. get("AUTHOR", []) or raw.get("authors", []),
                "REVIEWER": raw.get("REVIEWER", []) or raw.get("reviewers", []),
                "APPROVER": raw.get("APPROVER", []) or raw.get("approvers", []),
            }
        except Exception as ex:
            logger.error(f"Error getting assignees: {ex}")
            return {"AUTHOR": [], "REVIEWER":  [], "APPROVER": []}

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
            (success:  bool, error_msg: Optional[str])
        """
        valid, error_msg = self. validate_assignments(assignments)
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
            logger.error(f"Error setting assignees: {ex}")
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
        if not assignments.approvers:
            return False, "Mindestens ein Freigeber erforderlich."

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
            List of user dicts with keys: id, username, email, full_name
        """
        # Strategy 1: Use RBAC service if available
        if self._rbac:
            try:
                users = self._rbac.list_users()
                if users:
                    logger.debug(f"Got {len(users)} users from RBAC service")
                    return self._normalize_users(users)
            except Exception as ex:
                logger. debug(f"RBAC list_users failed: {ex}")

        # Strategy 2: Use user_provider callback
        if self._user_provider:
            try:
                users = self._user_provider()
                if users:
                    logger.debug(f"Got {len(users)} users from user_provider")
                    return self._normalize_users(users)
            except Exception as ex:
                logger. debug(f"user_provider failed: {ex}")

        # Strategy 3: Try to get UserManager directly
        try:
            from usermanagement.logic.user_manager import UserManager
            um = UserManager()
            all_users = um.get_all_users()
            if all_users:
                users = []
                for u in all_users:
                    user_dict = {
                        "id": str(getattr(u, "id", "") or ""),
                        "username": str(getattr(u, "username", "") or ""),
                        "email": str(getattr(u, "email", "") or ""),
                        "full_name": str(getattr(u, "full_name", "") or ""),
                    }
                    if user_dict["username"]:
                        users.append(user_dict)
                if users:
                    logger.debug(f"Got {len(users)} users from UserManager")
                    return users
        except Exception as ex:
            logger.debug(f"Direct UserManager failed: {ex}")

        # Strategy 4: Try AppContext
        try:
            from core.common.app_context import AppContext

            # Try user_manager attribute
            user_manager = getattr(AppContext, "user_manager", None)
            if user_manager and hasattr(user_manager, "get_all_users"):
                all_users = user_manager.get_all_users()
                if all_users:
                    users = self._normalize_users(all_users)
                    if users:
                        logger.debug(f"Got {len(users)} users from AppContext. user_manager")
                        return users

            # Fallback:  current user only
            current = getattr(AppContext, "current_user", None)
            if current:
                user_dict = self._user_to_dict(current)
                if user_dict. get("username"):
                    logger.debug("Returning only current user as fallback")
                    return [user_dict]

        except Exception as ex:
            logger.debug(f"AppContext user lookup failed: {ex}")

        logger.warning("No user source available - returning empty list")
        return []

    def _normalize_users(self, users) -> List[Dict[str, str]]:
        """Normalize user objects to list of dicts."""
        result = []
        for user in users:
            user_dict = self._user_to_dict(user)
            if user_dict. get("username"):
                result. append(user_dict)
        return result

    def _user_to_dict(self, user) -> Dict[str, str]:
        """Convert user object to standardized dict."""
        if isinstance(user, dict):
            return {
                "id": str(user.get("id", "") or user.get("user_id", "") or ""),
                "username":  str(user.get("username", "") or user.get("name", "") or ""),
                "email": str(user.get("email", "") or ""),
                "full_name": str(user.get("full_name", "") or user.get("display_name", "") or ""),
            }

        return {
            "id": str(getattr(user, "id", "") or getattr(user, "user_id", "") or ""),
            "username": str(getattr(user, "username", "") or getattr(user, "name", "") or ""),
            "email": str(getattr(user, "email", "") or ""),
            "full_name":  str(getattr(user, "full_name", "") or getattr(user, "display_name", "") or ""),
        }