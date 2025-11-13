"""
===============================================================================
List Controller – document listing and search
-------------------------------------------------------------------------------
Purpose:
    - Provide a thin UI controller for populating the document list and
      executing a simple search. No business logic; delegates to services.

Contract to the View:
    - view.render_document_list(rows: list[dict])  # rows contain id/title/status/updated

Inputs:
    - document_service: maps domain models to list-ready DTO/dicts.
===============================================================================
"""
from __future__ import annotations
from typing import Any, Dict, List


class DocumentListController:
    """
    UI-only controller for the document list area.

    Responsibilities:
        - Load initial list (no filters).
        - Apply a search query and re-render the list.

    Excludes:
        - No detail loading, policies, or persistence in here.
    """

    def __init__(self, view, doc_service) -> None:
        """
        Parameters
        ----------
        view : Any
            The GUI view exposing 'render_document_list'.
        doc_service : Any
            Service providing 'search_documents(query, ...)'.
        """
        self._view = view
        self._doc_svc = doc_service

    def load_document_list(self) -> None:
        """Load the initial document list with default search settings."""
        rows: List[Dict[str, Any]] = self._doc_svc.search_documents(query=None)
        self._view.render_document_list(rows)

    def action_search(self, query: str) -> None:
        """
        Execute a simple search on title/description and render the results.

        Parameters
        ----------
        query : str
            Free text; empty string is treated as None (no filter).
        """
        rows: List[Dict[str, Any]] = self._doc_svc.search_documents(query=query or None)
        self._view.render_document_list(rows)
