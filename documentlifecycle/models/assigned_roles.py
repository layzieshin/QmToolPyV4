from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from .ids import UserId

@dataclass(slots=True)
class AssignedRoles:
    """
    Per-document role assignments (who is responsible for THIS document).
    Distinct from global SystemRole.
    """
    editor_id: Optional[UserId] = None     # Ersteller/Bearbeiter
    reviewer_id: Optional[UserId] = None   # Prüfer
    publisher_id: Optional[UserId] = None  # Freigeber/Publisher
