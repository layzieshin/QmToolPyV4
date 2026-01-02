"""Workflow policy service (no IO).

Implements workflow transition validation based on policy configuration.
Reads from documents_workflow_transitions.json.
"""

from __future__ import annotations
from typing import List, Dict, Optional, Any
from pathlib import Path
import json

from documents.enum.document_status import DocumentStatus


class WorkflowPolicy:
    """
    Policy evaluation for workflow transitions.

    Loads transition rules from JSON configuration.
    """

    def __init__(
        self,
        *,
        transitions: List[Dict[str, Any]],
        forbidden_transitions: List[str]
    ):
        """
        Args:
            transitions: List of transition rules (from JSON)
            forbidden_transitions: List of forbidden transition patterns (e.g., "EFFECTIVE->DRAFT")
        """
        self._transitions = transitions or []
        self._forbidden = self._parse_forbidden(forbidden_transitions or [])

    @classmethod
    def load_from_directory(cls, directory: str | Path) -> "WorkflowPolicy":
        """
        Load workflow policy from documents_workflow_transitions.json.

        Args:
            directory: Directory containing policy files

        Returns:
            WorkflowPolicy instance
        """
        base = Path(directory)
        policy_file = base / "documents_workflow_transitions.json"

        data = {}
        if policy_file.exists():
            try:
                with policy_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}

        return cls(
            transitions=data. get("workflow_transitions", []),
            forbidden_transitions=data.get("forbidden_transitions", [])
        )

    def allowed_transitions(self, status: DocumentStatus) -> List[str]:
        """
        Return allowed action identifiers from the given status.

        Args:
            status: Current document status

        Returns:
            List of action IDs (e.g., ["submit_review", "archive"])
        """
        actions:  List[str] = []

        for rule in self._transitions:
            from_status = self._parse_status(rule.get("from"))

            if from_status != status:
                continue

            # Check if transition is forbidden
            to_status = self._parse_status(rule.get("to"))
            if self._is_forbidden(from_status, to_status):
                continue

            action = str(rule.get("action", "")).strip()
            if action:
                actions.append(action)

        return actions

    def next_status(self, *, action_id: str, status: DocumentStatus) -> Optional[DocumentStatus]:
        """
        Resolve the next status for a given action.

        Args:
            action_id: Action identifier
            status: Current status

        Returns:
            Next DocumentStatus or None if not found
        """
        action = (action_id or "").strip().lower()

        for rule in self._transitions:
            from_status = self._parse_status(rule.get("from"))
            rule_action = str(rule.get("action", "")).strip().lower()

            if from_status == status and rule_action == action:
                return self._parse_status(rule.get("to"))

        return None

    def requires_signature(self, action_id: str, doc_type: str = "") -> bool:
        """
        Determine whether signatures are required for the action.

        Args:
            action_id: Action identifier
            doc_type: Document type (for type-specific rules)

        Returns:
            True if signature required
        """
        action = (action_id or "").strip().lower()

        # Standard actions that typically require signatures
        signature_actions = {
            "submit_review",
            "approve",
            "publish",
        }

        return action in signature_actions

    def requires_reason(self, action_id: str, target_status: Optional[DocumentStatus] = None) -> bool:
        """
        Determine whether a reason is required for the action.

        Args:
            action_id: Action identifier
            target_status: Target status (optional)

        Returns:
            True if reason required
        """
        action = (action_id or "").strip().lower()

        # Actions that always require reason
        reason_actions = {
            "create_revision",
            "archive",
            "obsolete",
        }

        if action in reason_actions:
            return True

        # Check if target status requires reason
        if target_status:
            if target_status in (DocumentStatus.OBSOLETE, DocumentStatus.ARCHIVED):
                return True

        # Check transition rules
        for rule in self._transitions:
            rule_action = str(rule.get("action", "")).strip().lower()
            if rule_action == action:
                requirement = rule.get("requirement")
                if requirement:
                    return True

        return False

    def _is_forbidden(self, from_status: DocumentStatus, to_status:  DocumentStatus) -> bool:
        """Check if transition is in forbidden list."""
        for forbidden_from, forbidden_to in self._forbidden:
            if forbidden_from == from_status:
                if forbidden_to is None or forbidden_to == to_status:
                    return True
        return False

    @staticmethod
    def _parse_status(value: Any) -> DocumentStatus:
        """Parse status string to DocumentStatus enum."""
        if isinstance(value, DocumentStatus):
            return value

        raw = str(value or "").strip().upper()

        try:
            return DocumentStatus[raw]
        except KeyError:
            # Fallback to DRAFT
            return DocumentStatus.DRAFT

    @staticmethod
    def _parse_forbidden(items: List[str]) -> List[tuple[DocumentStatus, Optional[DocumentStatus]]]:
        """
        Parse forbidden transition patterns.

        Examples:
        - "EFFECTIVE->DRAFT" → (EFFECTIVE, DRAFT)
        - "ARCHIVED->*" → (ARCHIVED, None)
        """
        result:  List[tuple[DocumentStatus, Optional[DocumentStatus]]] = []

        for item in items:
            raw = str(item).strip()
            if "->" not in raw:
                continue

            parts = raw.split("->", 1)
            left = parts[0].strip()
            right = parts[1].strip() if len(parts) > 1 else ""

            from_status = WorkflowPolicy._parse_status(left)

            if right in ("*", ""):
                # Wildcard: all transitions from this status are forbidden
                result.append((from_status, None))
            else:
                to_status = WorkflowPolicy._parse_status(right)
                result.append((from_status, to_status))

        return result