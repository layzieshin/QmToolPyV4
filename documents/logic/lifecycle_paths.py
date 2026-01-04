from __future__ import annotations

"""Lifecycle path resolver for the Documents module.

This module centralizes the directory and filename conventions for document working copies.

Design goals:
- Deterministic, testable paths.
- No GUI / DB access (pure path policy).
- No globals/singletons; consumers instantiate and pass in base paths.

Target layout (default):
    ./documents/LifeCycle/<DOC_CODE>/V<version>/
    ./documents/LifeCycle/Archive/<DOC_CODE>/V<version>/

Where DOC_CODE is an 8-character identifier like 'C04VA001'.
"""

from dataclasses import dataclass
from enum import Enum
import re
from pathlib import Path
from typing import Optional


_DOC_CODE_RE = re.compile(r"^(?P<code>[A-Z0-9]{8})(?:[_-].*)?$")
_SAFE_COMPONENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


class ArtifactType(str, Enum):
    """Artifact type within a lifecycle version directory."""

    DOCX = "docx"
    PDF = "pdf"
    FINAL_PDF = "final_pdf"


@dataclass(frozen=True, slots=True)
class LifecycleRoots:
    """Root folders for lifecycle storage."""

    lifecycle_root: Path
    archive_root: Path

    @staticmethod
    def from_cwd() -> "LifecycleRoots":
        """Default roots based on current working directory."""
        base = Path.cwd() / "documents" / "LifeCycle"
        return LifecycleRoots(lifecycle_root=base, archive_root=base / "Archive")


class LifecyclePathResolver:
    """Resolves lifecycle paths for working copies and archived documents."""

    def __init__(self, roots: LifecycleRoots) -> None:
        self._roots = roots

    @property
    def roots(self) -> LifecycleRoots:
        return self._roots

    # -------------------------
    # Public API
    # -------------------------
    def ensure_base_dirs(self) -> None:
        """Ensure base lifecycle directories exist."""
        self._roots.lifecycle_root.mkdir(parents=True, exist_ok=True)
        self._roots.archive_root.mkdir(parents=True, exist_ok=True)

    def version_dir(self, *, document_code: str, version: str, archived: bool = False) -> Path:
        """Return the directory for a document code and version."""
        code = self.normalize_document_code(document_code)
        vdir = self._version_dir_name(version)

        root = self._roots.archive_root if archived else self._roots.lifecycle_root
        path = root / code / vdir
        return path

    def artifact_path(
        self,
        *,
        document_code: str,
        version: str,
        title: Optional[str],
        artifact: ArtifactType,
        archived: bool = False,
    ) -> Path:
        """Return the full file path for a lifecycle artifact.

        Args:
            document_code: 8-char code (e.g. 'C04VA001').
            version: version string (e.g. '1.0' or 'V1.0').
            title: human-readable document title (e.g. 'Bestellungen'). May be None/empty.
            artifact: ArtifactType.DOCX / PDF / FINAL_PDF.
            archived: if True, use archive root.

        Returns:
            Absolute/relative Path depending on provided roots.
        """
        base_dir = self.version_dir(document_code=document_code, version=version, archived=archived)
        ext = self._artifact_extension(artifact)

        is_final = artifact == ArtifactType.FINAL_PDF
        filename = self.build_filename(document_code=document_code, title=title, version=version, ext=ext, signed=is_final)
        return base_dir / filename

    # -------------------------
    # Naming helpers
    # -------------------------
    @staticmethod
    def normalize_document_code(value: str) -> str:
        """Normalize and validate a document code.

        Accepts strings like:
          - 'C04VA001'
          - 'c04va001'
          - 'C04VA001_Bestellungen.docx'

        Returns:
            Uppercase 8-char code.

        Raises:
            ValueError: if no valid 8-char code could be derived.
        """
        if not value:
            raise ValueError("document_code is required")

        candidate = value.strip()
        # If a full filename is passed, take the stem's beginning.
        candidate = Path(candidate).stem

        m = _DOC_CODE_RE.match(candidate.upper())
        if not m:
            raise ValueError(f"Invalid document code: {value!r}. Expected 8 alphanumeric chars, e.g. 'C04VA001'.")
        return m.group("code")

    @staticmethod
    def parse_document_code_from_filename(filename: str) -> Optional[str]:
        """Try to parse an 8-char document code from a filename or stem."""
        if not filename:
            return None
        stem = Path(filename).stem.upper()
        m = _DOC_CODE_RE.match(stem)
        return m.group("code") if m else None

    @staticmethod
    def build_filename(*, document_code: str, title: Optional[str], version: str, ext: str, signed: bool) -> str:
        """Build a canonical filename for a lifecycle artifact.

        Canonical form:
            <CODE>_<TITLE>_v<version>[ _signed].<ext>

        Rules:
        - CODE is always present (8 chars).
        - TITLE is optional; if missing, filename starts with CODE.
        - If TITLE already starts with '<CODE>_' we do not repeat the CODE.
        - version accepts '1.0' or 'V1.0'; written as 'v1.0' in filename.
        - signed=True appends exactly one '_signed' (idempotent normalization).
        """
        code = LifecyclePathResolver.normalize_document_code(document_code)

        version_norm = LifecyclePathResolver._version_value(version)
        version_part = f"v{version_norm}"

        safe_title = (title or "").strip()
        safe_title = LifecyclePathResolver._safe_component(safe_title) if safe_title else ""

        if safe_title:
            if safe_title.upper().startswith(f"{code}_"):
                base = safe_title
            else:
                base = f"{code}_{safe_title}"
        else:
            base = code

        # Avoid duplicating a previous version segment if callers pass a full base name.
        # We only strip trailing _v<...> if it matches our pattern.
        base = re.sub(r"_v\d+(?:\.\d+)?$", "", base, flags=re.IGNORECASE)

        filename = f"{base}_{version_part}"
        if signed:
            filename = LifecyclePathResolver._ensure_single_signed_suffix(filename)

        ext_clean = ext if ext.startswith(".") else f".{ext}"
        return f"{filename}{ext_clean}"

    # -------------------------
    # Internal helpers
    # -------------------------
    @staticmethod
    def _safe_component(value: str) -> str:
        value = value.strip()
        if not value:
            return ""
        # Replace whitespace/unsafe chars with '_', then collapse duplicates.
        cleaned = _SAFE_COMPONENT_RE.sub("_", value)
        cleaned = re.sub(r"_+", "_", cleaned).strip("_")
        return cleaned

    @staticmethod
    def _ensure_single_signed_suffix(stem: str) -> str:
        # Remove any trailing repeated '_signed' segments and re-add one.
        cleaned = re.sub(r"(?:_signed)+$", "", stem, flags=re.IGNORECASE)
        return f"{cleaned}_signed"

    @staticmethod
    def _artifact_extension(artifact: ArtifactType) -> str:
        if artifact == ArtifactType.DOCX:
            return ".docx"
        if artifact in (ArtifactType.PDF, ArtifactType.FINAL_PDF):
            return ".pdf"
        raise ValueError(f"Unsupported artifact type: {artifact!r}")

    @staticmethod
    def _version_dir_name(version: str) -> str:
        v = LifecyclePathResolver._version_value(version)
        return f"V{v}"

    @staticmethod
    def _version_value(version: str) -> str:
        v = (version or "").strip()
        if not v:
            raise ValueError("version is required")
        if v.upper().startswith("V"):
            v = v[1:]
        v = v.strip()
        # We keep arbitrary versions, but enforce a simple safety check.
        if not re.match(r"^\d+(?:\.\d+)?$", v):
            raise ValueError(f"Invalid version format: {version!r}. Expected like '1.0' or 'V1.0'.")
        return v
