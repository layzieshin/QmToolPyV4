"""Signature policy service (no IO).

Evaluates required signatures per document type and action.
Reads from documents_document_types.json.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from pathlib import Path
import json


class SignaturePolicy:
    """Signature requirements for workflow steps."""

    def __init__(self, *, document_types: Dict[str, Dict[str, Any]]):
        """
        Args:
            document_types: Map of doc_type -> type configuration
        """
        self._document_types = {
            str(k): dict(v or {})
            for k, v in (document_types or {}).items()
        }

    @classmethod
    def load_from_directory(cls, directory: str | Path) -> "SignaturePolicy":
        """
        Load signature policy from documents_document_types.json.

        Args:
            directory: Directory containing policy files

        Returns:
            SignaturePolicy instance
        """
        base = Path(directory)
        types_file = base / "documents_document_types.json"

        data = {}
        if types_file.exists():
            try:
                with types_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}

        return cls(document_types=data.get("document_types", {}))

    def required_roles(self, *, doc_type: str, action_id: str) -> List[str]:
        """
        Return module roles required to sign for this action.

        Args:
            doc_type: Document type (e.g., "SOP", "WI")
            action_id: Action identifier (e.g., "submit_review", "approve")

        Returns:
            List of role names (e.g., ["AUTHOR", "REVIEWER"])
        """
        action = (action_id or "").strip().lower()

        # Get type configuration
        type_config = self._document_types.get(doc_type, {})

        # Check if signatures are required for this type
        required_signatures = type_config.get("required_signatures", [])

        if not isinstance(required_signatures, list):
            return []

        # Filter signatures by action
        # Example format: {"action": "submit_review", "role": "AUTHOR"}
        roles:  List[str] = []

        for sig in required_signatures:
            if isinstance(sig, str):
                # Simple format: just action name
                if sig.strip().lower() == action:
                    # Default role mapping
                    role = self._default_role_for_action(action)
                    if role:
                        roles.append(role)
            elif isinstance(sig, dict):
                # Complex format: {action, role}
                sig_action = str(sig.get("action", "")).strip().lower()
                if sig_action == action:
                    role = str(sig.get("role", "")).strip().upper()
                    if role:
                        roles.append(role)

        return roles

    def requires_signature(self, *, doc_type: str, action_id: str) -> bool:
        """
        Check if signature is required for this action.

        Args:
            doc_type: Document type
            action_id: Action identifier

        Returns:
            True if signature required
        """
        return len(self.required_roles(doc_type=doc_type, action_id=action_id)) > 0

    @staticmethod
    def _default_role_for_action(action_id: str) -> Optional[str]:
        """
        Map action to default signing role.

        Args:
            action_id: Action identifier

        Returns:
            Role name or None
        """
        action = (action_id or "").strip().lower()

        mapping = {
            "submit_review": "AUTHOR",
            "approve": "REVIEWER",
            "publish": "APPROVER",
        }

        return mapping.get(action)