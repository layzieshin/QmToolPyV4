from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

from documents.models.document_models import DocumentStatus


@dataclass(frozen=True)
class TransitionRule:
    from_status: DocumentStatus
    to_status: DocumentStatus
    action: str
    condition: Optional[str] = None
    requirement: Optional[str] = None


class DocumentsPolicy:
    def __init__(
        self,
        *,
        transitions: Iterable[TransitionRule],
        forbidden_transitions: Iterable[str],
        role_actions: Dict[str, Iterable[str]],
        separation_of_duties: Dict[str, bool],
        document_types: Dict[str, Dict[str, object]],
    ) -> None:
        self._transitions = list(transitions)
        self._forbidden = self._parse_forbidden(forbidden_transitions)
        self._role_actions = {
            role.strip().upper(): {str(a).strip().lower() for a in actions or []}
            for role, actions in (role_actions or {}).items()
        }
        self._separation = {k: bool(v) for k, v in (separation_of_duties or {}).items()}
        self._document_types = {str(k): dict(v or {}) for k, v in (document_types or {}).items()}

    @classmethod
    def load_from_directory(cls, directory: str | Path) -> "DocumentsPolicy":
        base = Path(directory)
        transitions_data = _load_json(base / "documents_workflow_transitions.json")
        permissions_data = _load_json(base / "documents_permissions_policy.json")
        doc_types_data = _load_json(base / "documents_document_types.json")

        transitions = []
        for item in transitions_data.get("workflow_transitions", []):
            transitions.append(
                TransitionRule(
                    from_status=_parse_status(item.get("from")),
                    to_status=_parse_status(item.get("to")),
                    action=str(item.get("action") or "").strip(),
                    condition=item.get("condition"),
                    requirement=item.get("requirement"),
                )
            )

        return cls(
            transitions=transitions,
            forbidden_transitions=transitions_data.get("forbidden_transitions", []),
            role_actions=permissions_data.get("role_permissions", {}),
            separation_of_duties=permissions_data.get("separation_of_duties", {}),
            document_types=doc_types_data.get("document_types", {}),
        )

    def document_type(self, doc_type: str | None) -> Optional[Dict[str, object]]:
        if not doc_type:
            return None
        return self._document_types.get(str(doc_type))

    def transitions_from(self, status: DocumentStatus, doc_type: str) -> List[TransitionRule]:
        doc_cfg = self.document_type(doc_type)
        if not doc_cfg:
            return []
        out: List[TransitionRule] = []
        for rule in self._transitions:
            if rule.from_status != status:
                continue
            if not self._condition_matches(rule.condition, doc_cfg):
                continue
            if self.is_transition_forbidden(rule.from_status, rule.to_status):
                continue
            out.append(rule)
        return out

    def is_transition_forbidden(self, from_status: DocumentStatus, to_status: DocumentStatus) -> bool:
        for frm, to in self._forbidden:
            if frm == from_status and (to is None or to == to_status):
                return True
        return False

    def action_allowed_for_roles(self, action_id: str, roles: Iterable[str]) -> bool:
        action = (action_id or "").strip().lower()
        if not action:
            return False
        allowed_roles = {
            role
            for role, actions in self._role_actions.items()
            if action in actions or any(alias in actions for alias in _action_aliases(action))
        }
        return bool({r.upper() for r in roles} & allowed_roles)

    def violates_separation_of_duties(
        self,
        *,
        action_id: str,
        actor_id: str | None,
        owner_id: str | None,
        doc_type: str,
    ) -> bool:
        if not actor_id or not owner_id:
            return False
        actor = actor_id.strip().lower()
        owner = owner_id.strip().lower()
        if not actor or not owner:
            return False
        doc_cfg = self.document_type(doc_type) or {}

        if (action_id or "").strip().lower() == "review" and self._separation.get("no_self_review", False):
            return actor == owner

        if (action_id or "").strip().lower() in {"approve", "publish"} and self._separation.get("no_self_approval", False):
            if bool(doc_cfg.get("allow_self_approval", False)):
                return False
            return actor == owner

        return False

    def requires_reason(self, action_id: str, target_status: DocumentStatus) -> bool:
        action = (action_id or "").strip().lower()
        for rule in self._transitions:
            if rule.action == action and rule.to_status == target_status:
                if rule.requirement:
                    return True
        return target_status in {DocumentStatus.OBSOLETE, DocumentStatus.ARCHIVED} or action == "create_revision"

    def required_signatures(self, doc_type: str, action_id: str) -> List[str]:
        if (action_id or "").strip().lower() not in {"submit_review", "approve", "publish"}:
            return []
        cfg = self.document_type(doc_type) or {}
        required = cfg.get("required_signatures", [])
        if not isinstance(required, list):
            return []
        return [str(r) for r in required if str(r).strip()]

    def _condition_matches(self, condition: Optional[str], doc_cfg: Dict[str, object]) -> bool:
        if not condition:
            return True
        cond = str(condition).strip().lower()
        if cond.startswith("document_type.requires_review"):
            expected = cond.split("==", 1)[-1].strip()
            wants = expected == "true"
            return bool(doc_cfg.get("requires_review", False)) == wants
        return False

    @staticmethod
    def _parse_forbidden(items: Iterable[str]) -> List[tuple[DocumentStatus, Optional[DocumentStatus]]]:
        out: List[tuple[DocumentStatus, Optional[DocumentStatus]]] = []
        for item in items or []:
            raw = str(item)
            if "->" not in raw:
                continue
            left, right = [s.strip() for s in raw.split("->", 1)]
            from_status = _parse_status(left)
            if right == "*" or right == "":
                out.append((from_status, None))
            else:
                out.append((from_status, _parse_status(right)))
        return out


def _load_json(path: Path) -> Dict[str, object]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}


def _parse_status(value: object) -> DocumentStatus:
    raw = str(value or "").strip().upper()
    try:
        return DocumentStatus[raw]
    except KeyError:
        return DocumentStatus.DRAFT


def _action_aliases(action_id: str) -> Set[str]:
    action = (action_id or "").strip().lower()
    mapping = {
        "create_revision": {"create_revision", "edit_revision"},
        "archive": {"archive", "obsolete"},
    }
    return mapping.get(action, {action})
