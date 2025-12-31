# documentlifecycle/logic/services/document_service.py
"""
===============================================================================
DocumentService – read-only facade for listing/searching/fetching documents
-------------------------------------------------------------------------------
Purpose:
    Provide a thin, UI-friendly read side for the Document Lifecycle feature.
    - Converts domain models to lightweight DTOs for the view.
    - Offers search and details retrieval without exposing repository internals.

Non-Goals:
    - No mutation (create/update/delete) in this service.
    - No workflow decisions (policies live elsewhere).

Robustness:
    - Uses a _safe_log() helper that NEVER breaks the UI even if the project's
      logger has an unexpected signature. Only positional args are used.

Integration:
    - Consumed by controllers (list/details) to render UI.
    - Composed with RoleRepository to enrich details with assigned users.

SRP:
    - One responsibility: read-only document data adaptation for the GUI.
===============================================================================
"""
from __future__ import annotations

from typing import List, Optional, Callable, Dict, Any, Mapping
from datetime import datetime
from dataclasses import asdict, is_dataclass
from enum import Enum

from documentlifecycle.logic.repository.document_repository import DocumentRepository
from documentlifecycle.logic.repository.role_repository import RoleRepository
from documentlifecycle.models.mappers import to_list_item_dto, to_details_dto
from documentlifecycle.models.document_status import DocumentStatus
from documentlifecycle.models.document_type import DocumentType

# Optional project logger; must not break even if signature differs
try:
    from core.qm_logging.logic.logger import logger  # type: ignore
except Exception:  # pragma: no cover
    class _NoopLogger:
        def log(self, *args, **kwargs) -> None:
            pass
    logger = _NoopLogger()  # type: ignore


# -----------------------------------------------------------------------------
# Helpers: DTO normalization for the view (enums → value, datetime → ISO)
# -----------------------------------------------------------------------------
def _norm_value(v: Any) -> Any:
    """Normalize values for the view: Enum->value, datetime->iso, keep None."""
    if isinstance(v, Enum):
        return v.value
    if isinstance(v, datetime):
        try:
            return v.isoformat(timespec="seconds")
        except Exception:
            return v.isoformat()
    return v


def _to_view_dict(dto_obj: Any) -> dict:
    """
    Convert a DTO (dataclass or plain object) into a plain dict with
    normalized values (enums/datetimes). Works recursively.
    """
    # 1) dataclass → asdict
    if is_dataclass(dto_obj):
        data = asdict(dto_obj)
    # 2) fallback: __dict__ if available
    elif hasattr(dto_obj, "__dict__"):
        data = dict(dto_obj.__dict__)
    else:
        # last resort: repr to avoid crashes
        return {"repr": repr(dto_obj)}

    def _walk(x: Any) -> Any:
        if isinstance(x, Mapping):
            return {k: _walk(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return type(x)(_walk(v) for v in x)
        return _norm_value(x)

    return _walk(data)


class DocumentService:
    """
    Read-only facade (DTO adapter) over repositories.

    Parameters
    ----------
    repo : DocumentRepository
        Source for document models.
    roles : RoleRepository
        Source for per-document role assignments (used in details view).
    resolve_user_display : Optional[Callable[[int | None], str]]
        Optional callback to map user ids to display strings.
    """

    def __init__(
        self,
        repo: DocumentRepository,
        roles: RoleRepository,
        resolve_user_display: Optional[Callable[[int | None], str]] = None,
    ) -> None:
        self._repo = repo
        self._roles = roles
        self._resolve = resolve_user_display or (lambda uid: f"User {uid}" if uid is not None else "-")

    # ------------------------------------------------------------------ #
    # Internal robust logging (positional args only)
    # ------------------------------------------------------------------ #
    def _safe_log(self, source: str, action: str, **fields: Any) -> None:
        """
        Serialize fields to a single message string and call logger.log only
        with positional parameters. Any error is swallowed.

        This prevents TypeError like: logger.log(..., query="abc")
        """
        try:
            message = " | ".join(f"{k}={v}" for k, v in fields.items())
            try:
                logger.log(source, action, message)  # type: ignore[arg-type]
            except TypeError:
                # Fallback: try with an extra positional placeholder
                logger.log(source, action, message, None)  # type: ignore[arg-type]
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Use cases (read-only)
    # ------------------------------------------------------------------ #
    def search_documents(
        self,
        query: str | None,
        status: Optional[DocumentStatus] = None,
        doc_type: Optional[DocumentType] = None,
        last_action_since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search documents and return light-weight dicts for the list UI.

        Returns
        -------
        list[dict]
            Each dict contains at least: id, title, status, updated
            (shape comes from the list-item DTO).
        """
        docs = self._repo.search(query, status, doc_type, last_action_since)
        dtos = [to_list_item_dto(d) for d in docs]
        rows: List[Dict[str, Any]] = [
            dict(id=x.id, title=x.title, status=x.status, updated=x.updated) for x in dtos
        ]
        self._safe_log("DocService", "Search", rows=len(rows), q=(query or ""))
        return rows

    # == vollständige Datei wie zuletzt geliefert, hier nur der get_details()-Teil angepasst ==

    def get_details(self, doc_id: int) -> dict | None:
        """
        Return a view-ready dict with all details for the given document id.
        - Loads model & role assignments
        - Builds Details DTO
        - Serializes safely to a dict (supports dataclass slots)
        - Enriches with 'code' from repository (model may not hold code yet)
        """
        doc = self._repo.get_by_id(doc_id)
        if not doc:
            return None

        try:
            assigned = self._roles.get_assignments(doc_id)
            if assigned:
                doc.roles = assigned
        except Exception:
            pass

        dto = to_details_dto(doc, resolve_user_display=self._resolve)
        result = _to_view_dict(dto)

        # NEW: enrich with code from DB (non-breaking)
        try:
            code = getattr(self._repo, "get_code_for_id")(doc_id)
            if code is not None:
                result["code"] = code
        except Exception:
            pass

        return result
