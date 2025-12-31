"""core/contracts/licensing.py
==========================

Licensing contracts.

Goal: local-first licensing today, but easily swappable for an online provider
later by programming against interfaces.

This ABC does NOT prescribe a specific licensing model; it captures the minimal
operations needed by features and the framework.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class LicenseState:
    """Represents the evaluated license state for a feature/module."""

    is_valid: bool
    reason: str = ""
    expires_at: Optional[datetime] = None


class ILicenseProvider(ABC):
    """Service that validates licenses for features."""

    @abstractmethod
    def validate_feature(self, feature_id: str) -> LicenseState:
        """Return license state for a given feature id."""


class ILicensableFeature(ABC):
    """A feature that can be gated by a license."""

    @property
    @abstractmethod
    def feature_id(self) -> str:
        """The feature identifier used for licensing checks."""
