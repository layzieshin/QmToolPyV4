documentlifecycle/logic/README_DEV.md (Markdown, zum Einlegen)
# Document Lifecycle – Logic Layer Guide (Developer Notes)

**Scope (M1/M2):** read-side services, policy-driven UI state, thin controllers, and SQLite-backed repositories for documents, comments, and role assignments. No heavy workflow mutations yet.

---

## Architecture Overview



controllers/
├── document_controller.py # Facade (stable API for the view)
├── list_controller.py # Search/List (UI-only)
├── details_controller.py # Details + UI-state application
├── workflow_controller.py # Start/Abort/Sign placeholders
└── actions_controller.py # Read/Print/Archive/Roles placeholders

logic/
├── services/
│ ├── document_service.py # Read-only DTO adapter for documents
│ └── comment_service.py # UI adapter for comments (list/add)
├── policy/
│ ├── permission_policy.py # System roles: start/abort/archive/roles
│ └── workflow_policy.py # Phase & validity rules (type-agnostic)
├── viewstate/
│ └── ui_state.py # Flags & hints for the view
├── adapters/
│ ├── appcontext_user_provider.py# Host bridge → CurrentUser
│ └── current_user_provider.py # Protocol + default dev provider
└── repository/
├── document_repository.py # Protocol
├── comment_repository.py # Protocol
├── role_repository.py # Protocol
└── sqlite/
├── base_sqlite_repo.py # Connection helper (PRAGMAs)
├── document_repository_sqlite.py# Read-only docs (+DDL)
├── comment_repository_sqlite.py # Comments table
└── role_repository_sqlite.py # Role assignments table


**SRP & MVC:**  
- **Controllers** are UI-only and orchestrate services; they do not contain domain rules.  
- **Services** adapt repositories to UI needs (DTOs) and call **Policies** for decisions.  
- **Policies** are pure, testable logic (no DB access except `RoleRepository` reads in `WorkflowPolicy`).  
- **ViewState** is the contract consumed by the GUI to show/hide buttons.  
- **Adapters** decouple policy/user contracts from the host’s AppContext.  
- **Repositories** define contracts; SQLite impls ship a minimal schema for demos/tests.

---

## Data Flow (read-side)

1. `list_controller` → `DocumentService.search_documents()` → List DTOs for the view.  
2. `details_controller` → `DocumentService.get_details()` → Detail DTO → render in view.  
3. `details_controller` → `UIStateService.compute(doc_id, user, starter_id)` → `DocumentLifecycleUIState`  
    - uses `PermissionPolicy` (system roles)  
    - uses `WorkflowPolicy` (phase/sign/validity via `RoleRepository`)  
    - the view (BottomBar) receives visibility flags.

---

## Policies (Decisions Implemented)

- **PermissionPolicy**:  
  - Start = Admin/QMB or explicit flag `can_start_workflow`.  
  - Abort = Starter or Admin/QMB.  
  - Edit roles = Admin/QMB.  
  - Archive = Admin/QMB.

- **WorkflowPolicy**:  
  - Strict statuses: `DRAFT → IN_REVIEW → APPROVED → PUBLISHED → ARCHIVED`.  
  - Multiple reviewers/approvers allowed.  
  - Reviewer must **not** also act as sole approver in same cycle.  
  - `is_expired()` and placeholder `can_extend_without_change()`.

---

## Logging

`DocumentService` and `CommentService` use a `_safe_log()` helper to avoid TypeErrors with the project logger. Only positional arguments are passed; logging must never crash the UI.

---

## Extending the Module

- **Add actions**: create a new SRP controller or service; keep the facade stable.  
- **Add fields**: extend Models/DTOs; update mappers; avoid leaking repository rows into the UI.  
- **Implement workflow writes**: introduce a `WorkflowService` with explicit transitions; policies stay read-only.  
- **Role editor**: use `RoleRepository.set_assignments()` (idempotent replace).

---

## Testing Notes

- Controllers are trivial to smoke-test (UI callbacks).  
- Policies are pure functions → easy unit tests.  
- SQLite repos create minimal DDL on first use → no external migrations needed for demos.  
- For user context in tests, use `DefaultCurrentUserProvider` or inject a stub.

---

## i18n

All user-visible strings in the GUI should be retrieved via `T("key")`.  
This logic layer stays English-only in code comments/docstrings as per project rules.

---
