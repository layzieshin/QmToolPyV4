"""core/contracts/settings.py
=========================

Settings contracts used for dependency injection and cross-feature access.

The repo currently contains a concrete SettingsManager with:
- get(namespace, key, fallback, user_specific, user_id)
- set(namespace, key, value, user_specific, user_id)
- delete(namespace, key, user_specific, user_id)

This interface matches that API, so existing implementations can be adapted
without changing feature code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ISettingsManager(ABC):
    """High-level settings API (namespaced key-value store)."""

    @abstractmethod
    def get(
        self,
        namespace: str,
        key: str,
        fallback: Any | None = None,
        *,
        user_specific: bool = False,
        user_id: str | None = None,
    ) -> Any | None:
        """Return a stored value or fallback."""

    @abstractmethod
    def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        *,
        user_specific: bool = False,
        user_id: str | None = None,
    ) -> None:
        """Persist a value."""

    @abstractmethod
    def delete(
        self,
        namespace: str,
        key: str,
        *,
        user_specific: bool = False,
        user_id: str | None = None,
    ) -> None:
        """Delete a stored value."""
