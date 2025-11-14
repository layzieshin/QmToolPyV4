from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .ids import DocumentId, UserId
from .document_type import DocumentType
from .document_status import DocumentStatus
from .assigned_roles import AssignedRoles

@dataclass(slots=True)
class Document:
    """
    Aggregate root for a managed document.

    Notes:
    - 'version_label'  holds the major.minor like "1.3"
    - 'revision'       counts editorial changes inside same version (int)
    - 'status'         domain status (Draft/Review/Approved/Published/Archived)
    - 'roles'          per-document responsibilities (editor/reviewer/publisher)
    - date fields      map your sketch: publish/validity/edit/archive timestamps
    """

    # Identity / classification
    id: DocumentId
    title: str
    description: str
    doc_type: DocumentType

    # Lifecycle
    status: DocumentStatus
    version_label: str                # e.g., "1.3"
    revision: int                     # e.g., 7 (within the same version)
    file_path: str                    # absolute or project-relative path

    # People (per-document roles)
    roles: AssignedRoles = field(default_factory=AssignedRoles)

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    edited_at: Optional[datetime] = None          # last content edit (Editor)
    reviewed_at: Optional[datetime] = None        # when review finished
    published_at: Optional[datetime] = None       # Publikationsdatum
    valid_from: Optional[datetime] = None         # Gültig ab
    valid_until: Optional[datetime] = None        # Gültig bis (Ablaufdatum)

    # Archiving
    archived_at: Optional[datetime] = None
    archived_by: Optional[UserId] = None
    archive_reason: Optional[str] = None

    # Convenience flags ------------------------------------------------------
    def is_active_workflow_candidate(self) -> bool:
        """
        True if the business status implies a workflow can be active
        (Draft or InReview or Approved but not yet Published).
        """
        return self.status in {
            DocumentStatus.DRAFT,
            DocumentStatus.IN_REVIEW,
            DocumentStatus.APPROVED,
        }

    def is_publishable(self) -> bool:
        return self.status == DocumentStatus.APPROVED

    def is_archivable(self) -> bool:
        return self.status in {DocumentStatus.PUBLISHED, DocumentStatus.APPROVED}
