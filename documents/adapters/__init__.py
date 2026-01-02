"""Adapters for external dependencies.

Provides abstraction layers for:
- Database access (SQL-agnostic)
- File storage (filesystem/cloud-agnostic)
- Signatures (signature provider-agnostic)
"""

from documents.adapters.database_adapter import DatabaseAdapter
from documents.adapters.sqlite_adapter import SQLiteAdapter
from documents.adapters.storage_adapter import StorageAdapter
from documents.adapters.filesystem_storage_adapter import FilesystemStorageAdapter

# Signature adapter (already exists, keep as-is)
try:
    from documents.adapters.signature_adapter import SignatureAdapter
except ImportError:
    SignatureAdapter = None  # type: ignore

__all__ = [
    "DatabaseAdapter",
    "SQLiteAdapter",
    "StorageAdapter",
    "FilesystemStorageAdapter",
    "SignatureAdapter",
]