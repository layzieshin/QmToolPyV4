"""Document type specification DTO.

Defines document type configuration including workflow requirements,
approval rules, and signature requirements.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass(frozen=True)
class TypeSpec:
    """
    Immutable document type specification.

    Defines workflow behavior and requirements for a document type.
    """

    code: str
    """Type code (e.g., 'SOP', 'WI', 'FB', 'CL')"""

    label: str
    """Human-readable label (e.g., 'Standard Operating Procedure')"""

    requires_review: bool = True
    """Whether review step is mandatory in workflow"""

    requires_approval: bool = True
    """Whether approval step is mandatory in workflow"""

    allow_self_approval: bool = False
    """
    Whether document owner can approve their own document.
    
    Typically False for compliance reasons (separation of duties).
    May be True for low-risk document types (e.g., forms, checklists).
    """

    required_signatures: List[str] = field(default_factory=list)
    """
    List of workflow steps requiring digital signatures.
    
    Examples:
    - ['submit_review', 'approve', 'publish']
    - ['approve']  (only approval requires signature)
    - []  (no signatures required)
    """

    default_review_months: int = 24
    """Default review cycle in months"""

    auto_version_on_publish: bool = True
    """Whether to automatically bump version when publishing"""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """
    Additional type-specific configuration.
    
    Examples:
    - Template path
    - Allowed file formats
    - Custom validation rules
    - Retention period
    """

    def requires_signature_for(self, action: str) -> bool:
        """
        Check if signature is required for specific action.

        Args:
            action:  Action identifier (e.g., 'submit_review', 'approve')

        Returns:
            True if signature required
        """
        return action.lower().strip() in [s.lower().strip() for s in self.required_signatures]