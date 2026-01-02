"""Structure contract tests for the documents feature."""
from __future__ import annotations

from pathlib import Path


def test_structure_contract() -> None:
    """Fail if required scaffold files are missing."""
    root = Path(__file__).resolve().parents[1]
    required = [
        root / "enum" / "document_status.py",
        root / "enum" / "document_type.py",
        root / "enum" / "module_role.py",
        root / "dto" / "document_header.py",
        root / "dto" / "document_version.py",
        root / "dto" / "audit_event.py",
        root / "dto" / "type_spec.py",
        root / "dto" / "view_state.py",
        root / "services" / "policy" / "workflow_policy.py",
        root / "services" / "policy" / "permission_policy.py",
        root / "services" / "policy" / "signature_policy.py",
        root / "services" / "type_registry.py",
        root / "services" / "ui_state_service.py",
        root / "repository" / "sqlite" / "schema.sql",
        root / "adapters" / "storage_adapter.py",
        root / "adapters" / "signature_adapter.py",
        root / "exceptions" / "errors.py",
        root / "tests" / "test_structure_contract.py",
        root / "tests" / "test_workflow_policy.py",
        root / "tests" / "test_permission_policy.py",
    ]
    missing = [path for path in required if not path.exists()]
    assert not missing, f"Missing required files: {missing}"
