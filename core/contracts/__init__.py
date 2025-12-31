"""core.contracts

Central, stable interfaces (ABCs) used as the ONLY cross-feature public API.

Design goals:
- Features depend on contracts, not on concrete implementations from other features.
- Contracts are versionable and machine-readable via each feature's `contracts.json`.
- The application can validate integration by checking implementations against these ABCs.

This package intentionally contains only interfaces and shared type definitions.
"""
