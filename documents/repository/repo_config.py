"""Repository configuration."""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class RepoConfig:
    """Configuration for documents repository."""

    root_path: str
    """Root directory for document storage"""

    db_path: str
    """Path to SQLite database file"""

    id_prefix: str = "DOC"
    """Prefix for document IDs (e.g., "DOC" → "DOC-2024-0001")"""

    id_pattern: str = "{YYYY}-{seq:04d}"
    """Pattern for ID generation (supports {YYYY}, {seq:04d})"""

    review_months: int = 24
    """Default review cycle in months"""

    watermark_copy: str = "KONTROLLIERTE KOPIE"
    """Watermark text for controlled copies"""