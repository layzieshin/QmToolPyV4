"""Workflow policy service (no IO).

Implements workflow transition validation based on policy configuration.
Uses STRING comparison for status to avoid enum class mismatch issues.
"""

from __future__ import annotations
from typing import List, Dict, Optional, Any
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


class WorkflowPolicy:
    """
    Policy evaluation for workflow transitions.

    WICHTIG: Verwendet String-Vergleich für Status,
    um Enum-Klassen-Konflikte zu vermeiden.
    """

    def __init__(
        self,
        *,
        transitions: List[Dict[str, Any]],
        forbidden_transitions: List[str]
    ):
        self._transitions = transitions or []
        self._forbidden = self._parse_forbidden(forbidden_transitions or [])
        logger.debug(f"WorkflowPolicy:  {len(self._transitions)} transitions loaded")

    @classmethod
    def load_from_directory(cls, directory: str | Path) -> "WorkflowPolicy":
        """Load workflow policy from JSON file."""
        base = Path(directory)
        policy_file = base / "documents_workflow_transitions.json"

        data = {}
        if policy_file.exists():
            try:
                with policy_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info(f"Loaded workflow policy from {policy_file}")
            except Exception as ex:
                logger.error(f"Failed to load workflow policy: {ex}")
        else:
            logger.warning(f"Workflow policy not found:  {policy_file}, using defaults")
            data = cls._default_transitions()

        return cls(
            transitions=data.get("workflow_transitions", []),
            forbidden_transitions=data.get("forbidden_transitions", [])
        )

    @staticmethod
    def _default_transitions() -> Dict[str, Any]:
        """Default workflow transitions."""
        return {
            "workflow_transitions": [
                {"from": "DRAFT", "to": "REVIEW", "action": "submit_review"},
                {"from": "DRAFT", "to": "APPROVED", "action": "approve"},
                {"from": "REVIEW", "to": "APPROVED", "action": "approve"},
                {"from": "APPROVED", "to": "EFFECTIVE", "action": "publish"},
                {"from": "EFFECTIVE", "to": "REVISION", "action": "create_revision"},
                {"from":  "EFFECTIVE", "to": "OBSOLETE", "action": "obsolete"},
                {"from": "OBSOLETE", "to": "ARCHIVED", "action": "archive"},
                {"from": "REVISION", "to": "REVIEW", "action": "submit_review"},
            ],
            "forbidden_transitions": ["ARCHIVED->*"]
        }

    def allowed_transitions(self, status: Any) -> List[str]:
        """
        Return allowed action identifiers from the given status.

        Args:
            status: Current document status (Enum, string, or any object with . name)

        Returns:
            List of action IDs
        """
        status_name = self._to_status_name(status)
        actions:  List[str] = []

        for rule in self._transitions:
            from_name = str(rule.get("from", "")).strip().upper()

            if from_name != status_name:
                continue

            to_name = str(rule.get("to", "")).strip().upper()
            if self._is_forbidden(from_name, to_name):
                continue

            action = str(rule.get("action", "")).strip()
            if action and action not in actions:
                actions.append(action)

        logger.debug(f"allowed_transitions({status_name}): {actions}")
        return actions

    def next_status(self, *, action_id: str, status: Any) -> Optional[str]:
        """
        Resolve the next status name for a given action.

        Returns:
            Next status as STRING (not enum)
        """
        action = (action_id or "").strip().lower()
        status_name = self._to_status_name(status)

        for rule in self._transitions:
            from_name = str(rule.get("from", "")).strip().upper()
            rule_action = str(rule.get("action", "")).strip().lower()

            if from_name == status_name and rule_action == action:
                return str(rule.get("to", "")).strip().upper()

        return None

    def requires_signature(self, action_id: str, doc_type: str = "") -> bool:
        """
        Check if action requires signature.

        Signatur ist PFLICHT für:
        - submit_review
        - approve
        - publish
        """
        action = (action_id or "").strip().lower()

        signature_actions = {
            "submit_review",
            "approve",
            "publish",
        }

        return action in signature_actions

    def requires_reason(self, action_id: str, target_status: Optional[str] = None) -> bool:
        """Check if action requires a reason."""
        action = (action_id or "").strip().lower()

        reason_actions = {"create_revision", "archive", "obsolete", "back_to_draft"}
        if action in reason_actions:
            return True

        if target_status:
            target_name = self._to_status_name(target_status)
            if target_name in ("OBSOLETE", "ARCHIVED"):
                return True

        return False

    def _to_status_name(self, status: Any) -> str:
        """Convert any status representation to uppercase string."""
        if status is None:
            return ""
        if hasattr(status, 'name'):
            return str(status.name).upper()
        if hasattr(status, 'value'):
            return str(status.value).upper()
        return str(status).strip().upper()

    def _is_forbidden(self, from_name: str, to_name: str) -> bool:
        """Check if transition is forbidden."""
        for forbidden_from, forbidden_to in self._forbidden:
            if forbidden_from == from_name:
                if forbidden_to is None or forbidden_to == to_name:
                    return True
        return False

    @staticmethod
    def _parse_forbidden(items: List[str]) -> List[tuple[str, Optional[str]]]:
        """Parse forbidden transition patterns."""
        result:  List[tuple[str, Optional[str]]] = []

        for item in items:
            raw = str(item).replace(" ", "")
            if "->" not in raw:
                continue

            parts = raw.split("->", 1)
            left = parts[0].upper()
            right = parts[1].upper() if len(parts) > 1 else ""

            if right in ("*", ""):
                result.append((left, None))
            else:
                result.append((left, right))

        return result