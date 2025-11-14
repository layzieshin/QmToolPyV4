from __future__ import annotations
from datetime import datetime
from typing import Optional, Callable

from .document import Document
from .dto.document_list_item_dto import DocumentListItemDTO
from .dto.document_details_dto import DocumentDetailsDTO

def _fmt(dt: Optional[datetime]) -> Optional[str]:
    return dt.strftime("%Y-%m-%d") if dt else None

def to_list_item_dto(doc: Document) -> DocumentListItemDTO:
    version = f"{doc.version_label} (rev {doc.revision})"
    updated = _fmt(doc.updated_at) or "-"
    return DocumentListItemDTO(
        id=int(doc.id),
        title=doc.title,
        status=doc.status.value,
        doc_type=doc.doc_type.value,
        version=version,
        updated=updated,
    )

def to_details_dto(
    doc: Document,
    *,
    resolve_user_display: Callable[[Optional[int]], Optional[str]] = lambda uid: str(uid) if uid is not None else None,
) -> DocumentDetailsDTO:
    return DocumentDetailsDTO(
        id=int(doc.id),
        title=doc.title,
        description=doc.description,
        status=doc.status.value,
        doc_type=doc.doc_type.value,
        version=doc.version_label,
        revision=doc.revision,
        path=doc.file_path,
        editor=resolve_user_display(doc.roles.editor_id),
        reviewer=resolve_user_display(doc.roles.reviewer_id),
        publisher=resolve_user_display(doc.roles.publisher_id),
        edited_at=_fmt(doc.edited_at),
        reviewed_at=_fmt(doc.reviewed_at),
        published_at=_fmt(doc.published_at),
        valid_from=_fmt(doc.valid_from),
        valid_until=_fmt(doc.valid_until),
        archived_at=_fmt(doc.archived_at),
    )
