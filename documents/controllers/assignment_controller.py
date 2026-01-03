"""AssignmentController - handles role assignments per document.

Keine RBAC-Abhängigkeit - Benutzer kommen direkt aus UserManager.
"""

from __future__ import annotations
from typing import Callable, Dict, List, Optional, Tuple
import logging

from documents.dto.assignments import Assignments

logger = logging.getLogger(__name__)


class AssignmentController:
    """
    Verwaltet Rollenzuweisungen pro Dokument.

    Responsibilities:
    - Get/Set Assignees
    - Validate Assignments (Business Rules)
    - Get Available Users (aus UserManager)
    """

    def __init__(
        self,
        *,
        repository,
        user_provider: Optional[Callable[[], List[Dict[str, str]]]] = None
    ) -> None:
        """
        Args:
            repository: Documents repository
            user_provider:  Callable that returns list of user dicts
        """
        self._repo = repository
        self._user_provider = user_provider

    def get_assignees(self, doc_id: str) -> Dict[str, List[str]]:
        """Hole aktuelle Zuweisungen."""
        try:
            raw = self._repo.get_assignees(doc_id)
            return {
                "AUTHOR": raw.get("AUTHOR", []) or [],
                "REVIEWER": raw. get("REVIEWER", []) or [],
                "APPROVER":  raw.get("APPROVER", []) or [],
            }
        except Exception as ex:
            logger.error(f"Error getting assignees: {ex}")
            return {"AUTHOR": [], "REVIEWER":  [], "APPROVER": []}

    def set_assignees(
        self,
        doc_id: str,
        assignments: Assignments
    ) -> Tuple[bool, Optional[str]]:
        """Speichere Zuweisungen."""
        # Validate
        valid, error = self. validate_assignments(assignments)
        if not valid:
            return False, error

        try:
            mapping = {
                "AUTHOR": assignments. authors or [],
                "REVIEWER": assignments.reviewers or [],
                "APPROVER": assignments.approvers or [],
            }
            self._repo.set_assignees(doc_id, mapping)
            logger.info(f"Assignments set for {doc_id}: {mapping}")
            return True, None
        except Exception as ex:
            logger.error(f"Error setting assignees: {ex}")
            return False, f"Zuweisungsfehler: {ex}"

    def validate_assignments(
        self,
        assignments: Assignments
    ) -> Tuple[bool, Optional[str]]:
        """
        Validiere Zuweisungen.

        Business Rules:
        - Mindestens 1 Approver erforderlich
        - Reviewer ≠ Approver (Separation of Duties)
        """
        if not assignments.approvers:
            return False, "Mindestens ein Freigeber erforderlich."

        reviewers = set(assignments.reviewers or [])
        approvers = set(assignments.approvers or [])

        overlap = reviewers & approvers
        if overlap:
            return False, f"Prüfer und Freigeber dürfen nicht identisch sein: {', '.join(overlap)}"

        return True, None

    def get_available_users(self) -> List[Dict[str, str]]:
        """
        Hole verfügbare Benutzer für Rollenzuweisung.

        Strategien (in Reihenfolge):
        1. user_provider Callback
        2. Direkter UserManager Import
        3. Aktueller Benutzer als Fallback
        """
        # Strategy 1: Use provided callback
        if self._user_provider:
            try:
                users = self._user_provider()
                if users:
                    return users
            except Exception as ex:
                logger.debug(f"user_provider failed: {ex}")

        # Strategy 2: Direct UserManager import
        try:
            from usermanagement.logic.user_manager import UserManager
            um = UserManager()
            all_users = um.get_all_users()

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
            logger.debug(f"UserManager import failed: {ex}")

        # Strategy 3: Current user as fallback
        try:
            from core.common.app_context import AppContext
            current = getattr(AppContext, "current_user", None)
            if current:
                user_dict = {
                    "id": str(getattr(current, "id", "") or ""),
                    "username": str(getattr(current, "username", "") or ""),
                    "email": str(getattr(current, "email", "") or ""),
                    "full_name": str(getattr(current, "full_name", "") or ""),
                }
                if user_dict["username"]:
                    logger.debug("Returning current user as fallback")
                    return [user_dict]
        except Exception as ex:
            logger.debug(f"AppContext fallback failed: {ex}")

        logger.warning("No users available for assignment")
        return []