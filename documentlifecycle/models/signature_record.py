from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .ids import DocumentId, UserId

@dataclass(slots=True)
class SignatureRecord:
    """
    Logical record of a user's signature on a document (not the binary image).
    The binary/signature graphic lives elsewhere; this ties user, time, purpose.
    """
    document_id: DocumentId
    user_id: UserId
    purpose: str               # e.g., "AuthorSignOff", "ReviewSignOff", "FinalApproval"
    signed_at: datetime
    signature_file: Optional[str] = None  # path to stored signature image if needed
