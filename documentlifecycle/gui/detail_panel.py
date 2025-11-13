"""
===============================================================================
DocumentDetailPanel – right-side details (tabbed: Details, Comments)
-------------------------------------------------------------------------------
Zweck
    - UI-Only: Zeigt Dokument-Metadaten und (vorerst) einen Kommentar-Tab an.
    - Keine Business-Logik. Daten werden vom Controller geliefert.
    - Übersetzungs-Keys nutzen das Präfix "documentlifecycle.".

Design / SRP
    - Reine View: Felder rendern, defensiv gegen fehlende Keys.
    - Controller-Wiring:
        * set_controller(controller)  -> bevorzugt
        * attach_controller(...)      -> Legacy-Alias
        * attachController(...)       -> Legacy-Alias
        * attachcontroller(...)       -> Legacy-Alias
    - Public API:
        * set_controller(controller)
        * set_details(doc_id: int, details: dict | None)

Hinweis
    - Dieses Panel ruft den Controller aktuell nicht aktiv auf; das Wiring dient
      der Kompatibilität mit bestehendem Code, der attach_* erwartet.
===============================================================================
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, Optional

try:
    from core.common.app_context import T  # type: ignore
except Exception:  # pragma: no cover
    def T(key: str) -> str: return ""


class DocumentDetailPanel(ttk.Frame):
    """
    Detail-Ansicht für ein ausgewähltes Dokument (Tabs: Details, Kommentare).

    Öffentliche Methoden
    --------------------
    set_controller(controller: object) -> None
        Hängt optional einen Controller an (Kompatibilität / zukünftige Events).

    set_details(doc_id: int, details: dict | None) -> None
        Übergibt die anzuzeigenden Feldwerte. Fehlende Keys werden schonend
        behandelt und als "-" dargestellt.
    """

    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._current_id: Optional[int] = None
        self._controller: Optional[object] = None
        self._vars: dict[str, tk.StringVar] = {}

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Notebook-Struktur
        self._tabs = ttk.Notebook(self)
        self._tabs.grid(row=0, column=0, sticky="nsew")

        # --- Tab: Details -------------------------------------------------- #
        self._tab_details = ttk.Frame(self._tabs)
        self._tabs.add(self._tab_details, text=T("documentlifecycle.tab.details") or "Details")
        self._tab_details.columnconfigure(1, weight=1)

        # Felder (Label-Key, Dict-Key)
        self._fields = [
            ("documentlifecycle.field.code", "code"),
            ("documentlifecycle.field.title", "title"),
            ("documentlifecycle.field.doc_type", "doc_type"),
            ("documentlifecycle.field.status", "status"),
            ("documentlifecycle.field.version", "version_label"),
            ("documentlifecycle.field.revision", "revision"),
            ("documentlifecycle.field.path", "file_path"),
            ("documentlifecycle.field.created_at", "created_at"),
            ("documentlifecycle.field.updated_at", "updated_at"),
            ("documentlifecycle.field.edited_at", "edited_at"),
            ("documentlifecycle.field.reviewed_at", "reviewed_at"),
            ("documentlifecycle.field.published_at", "published_at"),
            ("documentlifecycle.field.valid_from", "valid_from"),
            ("documentlifecycle.field.valid_until", "valid_until"),
            ("documentlifecycle.field.archived_at", "archived_at"),
            ("documentlifecycle.field.archived_by", "archived_by"),
            ("documentlifecycle.field.archive_reason", "archive_reason"),
            ("documentlifecycle.field.roles.editor", "editor_display"),
            ("documentlifecycle.field.roles.reviewer", "reviewer_display"),
            ("documentlifecycle.field.roles.publisher", "publisher_display"),
        ]

        row = 0
        for label_key, dict_key in self._fields:
            ttk.Label(self._tab_details, text=(T(label_key) or label_key)).grid(
                row=row, column=0, sticky="w", padx=(8, 6), pady=3
            )
            var = tk.StringVar(value="-")
            self._vars[dict_key] = var
            ttk.Label(self._tab_details, textvariable=var).grid(
                row=row, column=1, sticky="ew", padx=(0, 8), pady=3
            )
            row += 1

        # --- Tab: Kommentare (Platzhalter) -------------------------------- #
        self._tab_comments = ttk.Frame(self._tabs)
        self._tabs.add(self._tab_comments, text=T("documentlifecycle.tab.comments") or "Kommentare")

        self._comments_list = tk.Listbox(self._tab_comments, height=8)
        self._comments_list.pack(fill="both", expand=True, padx=8, pady=8)

    # ------------------------------------------------------------------ #
    # Controller-Wiring (bevorzugt + Legacy-Aliase)
    # ------------------------------------------------------------------ #
    def set_controller(self, controller: object) -> None:
        """
        Hängt optional einen Controller an. Wird aktuell nicht aktiv genutzt,
        dient aber der Kompatibilität, falls externe Aufrufer attach_* erwarten.
        """
        self._controller = controller

    # Legacy-Alias-Varianten (Kompatibilität zu bestehendem Code):
    def attach_controller(self, controller: object) -> None:
        self.set_controller(controller)

    def attachController(self, controller: object) -> None:  # noqa: N802
        self.set_controller(controller)

    def attachcontroller(self, controller: object) -> None:
        self.set_controller(controller)

    # ------------------------------------------------------------------ #
    # Rendering-API
    # ------------------------------------------------------------------ #
    def set_details(self, doc_id: int, details: Dict[str, Any] | None) -> None:
        """
        Rendert die übergebenen Details im Panel.

        Parameters
        ----------
        doc_id : int
            Aktuelle Dokument-ID.
        details : dict | None
            Detailwerte. Fehlende Keys werden als "-" angezeigt.
        """
        self._current_id = doc_id
        data = details or {}

        def to_s(v: Any) -> str:
            if v is None:
                return "-"
            if hasattr(v, "value"):
                try:
                    return str(v.value)
                except Exception:
                    pass
            return str(v)

        for _, key in self._fields:
            self._vars[key].set(to_s(data.get(key)))

        # Rollen-Fallback (falls nicht bereits als *display geliefert)
        if not data.get("editor_display") and data.get("roles"):
            roles = data.get("roles") or {}
            self._vars["editor_display"].set(to_s(roles.get("editor")))
            self._vars["reviewer_display"].set(to_s(roles.get("reviewer")))
            self._vars["publisher_display"].set(to_s(roles.get("publisher")))

        # Kommentare (Platzhalter) leeren/befüllen
        try:
            self._comments_list.delete(0, "end")
            comments = data.get("comments") or []
            for c in comments:
                self._comments_list.insert("end", to_s(c))
        except Exception:
            pass
