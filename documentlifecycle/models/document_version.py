from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

from .ids import VersionId, DocumentId, UserId

@dataclass(slots=True)
class DocumentVersion:
    """
    Immutable file snapshot for a document version/revision.
    """
    id: VersionId
    document_id: DocumentId
    version_label: str     # "1.3"
    revision: int          # 7
    storage_path: str      # where the file is stored (DOCX/PDF)
    created_at: datetime
    created_by: UserId
