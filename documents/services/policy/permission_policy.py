"""documents/services/policy/permission_policy.py
=================================================

Permission policy for document-scoped module roles.

This policy does not perform any I/O and is fully deterministic.
"""
from __future__ import annotations

from typing import Iterable, Set

from documents.dto.document_type_spec import DocumentTypeSpec
from documents.enum.document_action import DocumentAction
from documents.enum.document_status import DocumentStatus
from documents.enum.module_role import ModuleRole


ROLE_ACTIONS: dict[ModuleRole, set[DocumentAction]] = {
    ModuleRole.AUTHOR: {
        DocumentAction.EDIT_METADATA,
        DocumentAction.EDIT_CONTENT,
        DocumentAction.SUBMIT_REVIEW,
    },
    ModuleRole.EDITOR: {
        DocumentAction.EDIT_METADATA,
        DocumentAction.EDIT_CONTENT,
        DocumentAction.CREATE_REVISION,
    },
    ModuleRole.REVIEWER: set(),
    ModuleRole.APPROVER: {
        DocumentAction.APPROVE,
        DocumentAction.PUBLISH,
        DocumentAction.OBSOLETE,
        DocumentAction.ARCHIVE,
    },
}


class PermissionPolicy:
    """Evaluates whether a user may perform an action based on module roles."""

    def can_perform(self, *, action_id: str, roles: Iterable[str]) -> bool:
        action = DocumentAction(action_id)
        for role in self._normalize_roles(roles):
            if action in ROLE_ACTIONS.get(role, set()):
                return True
        return False

    def can_edit_in_status(self, *, status: DocumentStatus, roles: Iterable[str]) -> bool:
        if status not in (DocumentStatus.DRAFT, DocumentStatus.REVISION):
            return False
        return bool({ModuleRole.AUTHOR, ModuleRole.EDITOR} & self._normalize_roles(roles))

    def violates_separation_of_duties(
        self,
        *,
        action_id: str,
        actor_id: str,
        owner_id: str,
        type_spec: DocumentTypeSpec,
    ) -> bool:
        action = DocumentAction(action_id)
        if action in (DocumentAction.APPROVE, DocumentAction.PUBLISH):
            return not type_spec.allow_self_approval and actor_id == owner_id
        return False

    @staticmethod
    def _normalize_roles(roles: Iterable[str]) -> Set[ModuleRole]:
        result: Set[ModuleRole] = set()
        for r in roles:
            try:
                result.add(ModuleRole(str(r).upper()))
            except ValueError:
                continue
        return result
