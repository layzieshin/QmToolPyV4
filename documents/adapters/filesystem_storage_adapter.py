"""Filesystem implementation of StorageAdapter.

Stores documents in local filesystem with structured directory layout.
"""

from __future__ import annotations
from typing import Optional
from pathlib import Path
import os
import shutil
import glob

from documents.adapters.storage_adapter import StorageAdapter


class FilesystemStorageAdapter(StorageAdapter):
    """Local filesystem implementation of StorageAdapter."""

    def __init__(self, root_path: str | Path):
        """
        Initialize filesystem storage.

        Args:
            root_path: Root directory for document storage
        """
        self._root = Path(root_path)
        self._root.mkdir(parents=True, exist_ok=True)

    def save_working_copy(self, *, doc_id: str, source_path: str, version: str) -> str:
        """Save working copy to version directory."""
        version_dir = self._root / doc_id / version
        version_dir.mkdir(parents=True, exist_ok=True)

        ext = Path(source_path).suffix
        dest_path = version_dir / f"{doc_id}_{version}{ext}"

        shutil.copy2(source_path, dest_path)

        return str(dest_path)

    def save_signed_pdf(self, *, doc_id: str, source_path: str, step: str, timestamp: str) -> str:
        """Save signed PDF to signed_pdfs directory."""
        signed_dir = self._root / doc_id / "signed_pdfs"
        signed_dir.mkdir(parents=True, exist_ok=True)

        dest_path = signed_dir / f"{doc_id}_{step}_{timestamp}.pdf"

        shutil.copy2(source_path, dest_path)

        return str(dest_path)

    def save_published_pdf(self, *, doc_id: str, source_path: str, version: str) -> str:
        """Save published PDF to published directory."""
        published_dir = self._root / doc_id / "published"
        published_dir.mkdir(parents=True, exist_ok=True)

        dest_path = published_dir / f"{doc_id}_{version}.pdf"

        shutil.copy2(source_path, dest_path)

        return str(dest_path)

    def get_file_path(self, *, doc_id: str, filename: str) -> Optional[str]:
        """Get path to specific file."""
        doc_dir = self._root / doc_id

        # Search in all subdirectories
        for dirpath, _, filenames in os.walk(doc_dir):
            if filename in filenames:
                return str(Path(dirpath) / filename)

        return None

    def file_exists(self, path: str) -> bool:
        """Check if file exists."""
        return Path(path).is_file()

    def list_files(self, *, doc_id: str, pattern: Optional[str] = None) -> list[str]:
        """List files for document."""
        doc_dir = self._root / doc_id

        if not doc_dir.exists():
            return []

        if pattern:
            # Use glob pattern
            matches = glob.glob(str(doc_dir / "**" / pattern), recursive=True)
            return matches
        else:
            # List all files
            files = []
            for dirpath, _, filenames in os.walk(doc_dir):
                for filename in filenames:
                    files.append(str(Path(dirpath) / filename))
            return files

    def copy_to_destination(self, *, source_path: str, dest_dir: str, filename: str) -> str:
        """Copy file to external destination."""
        dest_path = Path(dest_dir) / filename
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(source_path, dest_path)

        return str(dest_path)

    def get_document_directory(self, doc_id: str) -> str:
        """Get base directory for document."""
        doc_dir = self._root / doc_id
        doc_dir.mkdir(parents=True, exist_ok=True)
        return str(doc_dir)