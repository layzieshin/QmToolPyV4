# documents/gui/i18n.py
# Small translation helper to ensure readable labels when host translations are missing.

from __future__ import annotations

try:
    from core.common.app_context import T as _T  # host-provided translation function
except Exception:
    def _T(key: str) -> str | None:  # fallback shim if host T() not available at import time
        return None


def tr(key: str, default: str) -> str:
    """
    Safe translation getter with robust fallback:
    - If host returns None/empty -> use default
    - If host returns the key itself (common pattern) -> use default
    - If host returns a value that still looks like a key (dot-notation containing the key) -> use default
    """
    try:
        v = _T(key)  # may return None, empty string, or the key itself
    except Exception:
        v = None

    if v is None:
        return default

    s = str(v).strip()
    if not s:
        return default

    # Many i18n systems return the key if missing. Detect common cases.
    if s == key or s.startswith(key) or (("." in s) and (key in s)):
        return default

    return s
