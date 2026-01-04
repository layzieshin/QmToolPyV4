"""
DocumentCreationController - handles document creation and metadata updates.

Phase 2 change:
- create_from_template() now always creates a DOCX working copy in ./documents/LifeCycle/<CODE>/V1.0/
- DOTX templates are converted to a real DOCX package (not just renamed).
- current_file_path is set to the DOCX working copy path (via repository.create()).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple
import os
import shutil
import zipfile
from pathlib import Path

from documents.models.document_models import DocumentRecord
from documents.logic.lifecycle_paths import ArtifactType, LifecyclePathResolver, LifecycleRoots


class DocumentCreationController:
    """
    Handles document creation and metadata updates.

    Responsibilities:
    - Create from template
    - Import file
    - Update metadata

    SRP: Document lifecycle start, no workflow logic.
    """

    def __init__(
            self,
            *,
            repository: "DocumentsRepository",
            current_user_provider: Callable[[], Optional[object]]
    ) -> None:
        """
        Args:
            repository: Documents repository
            current_user_provider: Lambda that returns current user
        """
        self._repo = repository
        self._user_provider = current_user_provider

    def create_from_template(
            self,
            template_path: str,
            doc_type: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[DocumentRecord]]:
        """
        Create document from template.

        Phase 2 behavior:
        - Template must be DOCX or DOTX.
        - A working copy is created in the LifeCycle folder structure:
              ./documents/LifeCycle/<DOC_CODE>/V1.0/<DOC_CODE>_<TITLE>_v1.0.docx
        - If the template is DOTX, it is converted to a real DOCX (OOXML content type fixed).
        - The repository record is created with:
              current_file_path = <working_copy_docx>
              doc_code          = parsed from filename (8 chars, e.g. C04VA001)

        NOTE:
        - This method enforces presence of an 8-char document code in the template filename.
          If missing, user must provide metadata in the (later) metadata dialog flow.

        Args:
            template_path: Path to template (DOCX/DOTX)
            doc_type: Document type (must be allowed by repository constraint)

        Returns:
            (success: bool, error_msg: Optional[str], record: Optional[DocumentRecord])
        """
        if not os.path.isfile(template_path):
            return False, f"Template nicht gefunden: {template_path}", None

        # Allow DOCX and DOTX templates
        lp = template_path.lower()
        if not (lp.endswith(".docx") or lp.endswith(".dotx")):
            return False, "Nur DOCX- oder DOTX-Templates werden unterstützt.", None

        # Normalize doc_type
        doc_type_norm = (doc_type or "").strip()

        # If repo has allowed types (new world), enforce them early with a clean error
        allowed = ()
        try:
            allowed = tuple(getattr(getattr(self._repo, "_cfg", None), "allowed_doc_types", ()) or ())
        except Exception:
            allowed = ()

        if not doc_type_norm:
            if allowed:
                doc_type_norm = allowed[0]
            else:
                return False, "Kein Dokumenttyp angegeben.", None

        if allowed and doc_type_norm not in allowed:
            return False, f"Ungültiger Dokumenttyp '{doc_type_norm}'. Erlaubt: {', '.join(allowed)}", None

        # ---- Determine document code & title from filename ----
        src_name = os.path.basename(template_path)
        resolver = LifecyclePathResolver(LifecycleRoots.from_cwd())

        doc_code = resolver.parse_document_code_from_filename(src_name)
        if not doc_code:
            return (
                False,
                "Die Dokumentenkennung (8-stellig, z.B. 'C04VA001') fehlt im Vorlagen-Dateinamen. "
                "Bitte Vorlage entsprechend benennen oder Metadaten im Dialog angeben.",
                None,
            )

        # Title: strip leading "<CODE>_" or "<CODE>-"
        stem = Path(src_name).stem
        upper_stem = stem.upper()
        # Remove leading code + separator if present
        title = stem
        if upper_stem.startswith(f"{doc_code}_") or upper_stem.startswith(f"{doc_code}-"):
            title = stem[len(doc_code) + 1:]
        title = (title or "").strip() or stem  # fallback

        # ---- Create lifecycle working copy path for initial version ----
        version = "1.0"  # initial version (repository currently starts with 1.0)
        try:
            resolver.ensure_base_dirs()
            target_docx_path = resolver.artifact_path(
                document_code=doc_code,
                version=version,
                title=title,
                artifact=ArtifactType.DOCX,
                archived=False,
            )
            target_docx_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as ex:
            return False, f"Fehler beim Ermitteln des LifeCycle-Pfads: {ex}", None

        # ---- Create working copy file ----
        try:
            if lp.endswith(".docx"):
                shutil.copy2(template_path, target_docx_path)
            else:
                # DOTX -> real DOCX conversion (OOXML content types)
                self._convert_dotx_to_docx(Path(template_path), target_docx_path)
        except Exception as ex:
            return False, f"Fehler beim Erstellen der Arbeitskopie: {ex}", None

        # ---- Create repository record pointing to the working copy ----
        try:
            user_id = self._get_user_id()
            record = self._repo.create(
                title=title,
                doc_type=doc_type_norm,
                user_id=user_id,
                file_path=str(target_docx_path),
                doc_code=doc_code,
            )
            return True, None, record
        except Exception as ex:
            return False, f"Fehler beim Erstellen: {ex}", None

    def import_file(
            self,
            file_path: str,
            doc_type: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[DocumentRecord]]:
        """
        Import existing DOCX file.

        Args:
            file_path: Path to DOCX
            doc_type: Document type (must be allowed by repository constraint)

        Returns:
            (success: bool, error_msg: Optional[str], record: Optional[DocumentRecord])
        """
        if not os.path.isfile(file_path):
            return False, "Datei nicht gefunden.", None

        if not file_path.lower().endswith(".docx"):
            return False, "Nur DOCX-Dateien werden unterstützt.", None

        # Normalize doc_type
        doc_type_norm = (doc_type or "").strip()

        # If repo has allowed types (new world), enforce them early with a clean error
        allowed = ()
        try:
            allowed = tuple(getattr(getattr(self._repo, "_cfg", None), "allowed_doc_types", ()) or ())
        except Exception:
            allowed = ()

        if not doc_type_norm:
            if allowed:
                doc_type_norm = allowed[0]
            else:
                return False, "Kein Dokumenttyp angegeben.", None

        if allowed and doc_type_norm not in allowed:
            return False, f"Ungültiger Dokumenttyp '{doc_type_norm}'. Erlaubt: {', '.join(allowed)}", None

        try:
            user_id = self._get_user_id()
            record = self._repo.create_from_file(
                title=None,  # Will be extracted from filename
                doc_type=doc_type_norm,
                user_id=user_id,
                src_file=file_path
            )
            return True, None, record
        except Exception as ex:
            return False, f"Fehler beim Import: {ex}", None

    def update_document_metadata(
            self,
            doc_id: str,
            metadata: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Update document metadata.

        Args:
            doc_id: Document ID
            metadata: Metadata dict (title, doc_type, area, process, next_review)

        Returns:
            (success: bool, error_msg: Optional[str])
        """
        try:
            user_id = self._get_user_id()
            data = {"doc_id": doc_id, **metadata}
            self._repo.update_metadata(data, user_id)
            return True, None
        except Exception as ex:
            return False, f"Metadaten-Update fehlgeschlagen: {ex}"

    def _get_user_id(self) -> Optional[str]:
        """Get current user ID."""
        user = self._user_provider()
        if not user:
            return None

        for attr in ("id", "user_id", "uid"):
            val = getattr(user, attr, None)
            if val:
                return str(val)
        return None

    @staticmethod
    def _convert_dotx_to_docx(src_dotx: Path, dest_docx: Path) -> None:
        """Convert a DOTX package to a real DOCX package.

        This is NOT a semantic conversion; DOTX and DOCX are both OOXML ZIP packages.
        The critical difference is the main document content type in [Content_Types].xml.

        Many converters reject DOTX even if renamed to .docx, because the content types still
        declare a template main part. We fix that by rewriting [Content_Types].xml.

        Raises:
            ValueError: if [Content_Types].xml is missing.
        """
        if not src_dotx.exists():
            raise FileNotFoundError(str(src_dotx))

        # Ensure destination folder exists
        dest_docx.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(src_dotx, "r") as zin:
            names = set(zin.namelist())
            if "[Content_Types].xml" not in names:
                raise ValueError("Invalid DOTX: missing [Content_Types].xml")

            content_types = zin.read("[Content_Types].xml").decode("utf-8", errors="replace")

            # Replace the template main content type with document main content type
            content_types = content_types.replace(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
            )

            # Write new DOCX package
            with zipfile.ZipFile(dest_docx, "w", compression=zipfile.ZIP_DEFLATED) as zout:
                for name in zin.namelist():
                    if name == "[Content_Types].xml":
                        zout.writestr(name, content_types)
                    else:
                        zout.writestr(name, zin.read(name))
