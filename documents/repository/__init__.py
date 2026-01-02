"""Repository layer for documents module.

Provides data access abstractions.
"""

from documents.repository.document_repository import DocumentRepository
from documents.repository.sqlite_document_repository import SQLiteDocumentRepository
from documents.repository.repo_config import RepoConfig

__all__ = [
    "DocumentRepository",
    "SQLiteDocumentRepository",
    "RepoConfig",
]