"""Storage adapter abstraction.

Defines interface for document file storage operations.
Allows switching between local filesystem, S3, Azure Blob, etc.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional
from pathlib import Path


class StorageAdapter(ABC):
    """Abstract storage adapter for document content."""

    @abstractmethod
    def save_working_copy(self, *, doc_id: str, source_path: str, version: str) -> str:
        """
        Persist a working copy to storage.

        Args:
            doc_id: Document ID
            source_path: Path to source file
            version: Version label (e.g., "1.0")

        Returns:
            Path/URI to stored file
        """
        raise NotImplementedError

    @abstractmethod
    def save_signed_pdf(self, *, doc_id: str, source_path: str, step:  str, timestamp: str) -> str:
        """
        Persist a signed PDF.

        Args:
            doc_id: Document ID
            source_path: Path to signed PDF
            step:  Workflow step (e.g., "submit_review", "approve")
            timestamp: Timestamp string

        Returns:
            Path/URI to stored PDF
        """
        raise NotImplementedError

    @abstractmethod
    def save_published_pdf(self, *, doc_id: str, source_path: str, version: str) -> str:
        """
        Persist a published PDF with version suffix.

        Args:
            doc_id: Document ID
            source_path: Path to PDF
            version: Version label

        Returns:
            Path/URI to stored PDF
        """
        raise NotImplementedError

    @abstractmethod
    def get_file_path(self, *, doc_id: str, filename: str) -> Optional[str]:
        """
        Get path to a specific file.

        Args:
            doc_id: Document ID
            filename:  Filename within document storage

        Returns:
            Path/URI to file or None if not found
        """
        raise NotImplementedError

    @abstractmethod
    def file_exists(self, path: str) -> bool:
        """
        Check if file exists in storage.

        Args:
            path: Path/URI to check

        Returns:
            True if file exists
        """
        raise NotImplementedError

    @abstractmethod
    def list_files(self, *, doc_id: str, pattern: Optional[str] = None) -> list[str]:
        """
        List files for a document.

        Args:
            doc_id: Document ID
            pattern: Optional glob pattern (e.g., "*.docx")

        Returns:
            List of file paths/URIs
        """
        raise NotImplementedError

    @abstractmethod
    def copy_to_destination(self, *, source_path: str, dest_dir: str, filename: str) -> str:
        """
        Copy file to external destination (e.g., controlled copy export).

        Args:
            source_path: Source file path/URI
            dest_dir:  Destination directory
            filename: Destination filename

        Returns:
            Path to copied file
        """
        raise NotImplementedError

    @abstractmethod
    def get_document_directory(self, doc_id: str) -> str:
        """
        Get base directory/path for a document.

        Args:
            doc_id:  Document ID

        Returns:
            Directory path/URI
        """
        raise NotImplementedError