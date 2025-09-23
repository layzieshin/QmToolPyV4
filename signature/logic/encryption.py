# signature/logic/encryption.py
from __future__ import annotations

from typing import Any, List
from cryptography.fernet import Fernet, InvalidToken
from core.settings.logic.settings_manager import SettingsManager

_FEATURE_ID = "core_signature"
_KEY_FIELD = "fernet_key"
_RING_FIELD = "fernet_key_ring"


def _persist(sm: SettingsManager) -> None:
    """Best-effort persist for diverse SettingsManager implementations."""
    for meth in ("persist", "save", "flush"):
        fn = getattr(sm, meth, None)
        if callable(fn):
            try:
                fn()
                break
            except Exception:
                pass


def _load_keyring(sm: SettingsManager) -> List[Fernet]:
    """
    Create a list of Fernet instances:
    - first entry is the current key (used for ENCRYPT),
    - remaining entries are legacy keys (used only for DECRYPT).
    Keys are stored as base64 strings (Fernet.generate_key()) in settings.
    """
    cur_key_str = sm.get(_FEATURE_ID, _KEY_FIELD, None)
    ring_raw = sm.get(_FEATURE_ID, _RING_FIELD, [])

    # Normalize ring list (can be list or JSON string, depending on SettingsManager)
    if isinstance(ring_raw, str):
        try:
            import json
            ring_list = json.loads(ring_raw) or []
        except Exception:
            ring_list = []
    elif isinstance(ring_raw, list):
        ring_list = ring_raw
    else:
        ring_list = []

    # Create key if missing (one-time)
    if not cur_key_str:
        cur_key_str = Fernet.generate_key().decode("ascii")
        sm.set(_FEATURE_ID, _KEY_FIELD, cur_key_str)
        sm.set(_FEATURE_ID, _RING_FIELD, [])
        _persist(sm)

    ferns: List[Fernet] = []
    try:
        ferns.append(Fernet(cur_key_str.encode("ascii")))
    except Exception:
        # If the stored value is already bytes, try raw
        if isinstance(cur_key_str, (bytes, bytearray)):
            ferns.append(Fernet(cur_key_str))
        else:
            raise

    for k in ring_list:
        try:
            if isinstance(k, str):
                ferns.append(Fernet(k.encode("ascii")))
            elif isinstance(k, (bytes, bytearray)):
                ferns.append(Fernet(k))
        except Exception:
            # ignore malformed legacy entries
            pass

    return ferns


def encrypt_bytes(sm: SettingsManager, data: bytes) -> bytes:
    """
    Encrypt 'data' using the CURRENT Fernet key (first entry in keyring).
    """
    ferns = _load_keyring(sm)
    return ferns[0].encrypt(data)


def decrypt_bytes(sm: SettingsManager, token: bytes) -> bytes:
    """
    Try to decrypt using CURRENT key first, then legacy keys.
    If all fail, accept legacy plain PNG/JPEG/GIF content as-is.
    Otherwise raise InvalidToken.
    """
    last_exc: Exception | None = None
    for f in _load_keyring(sm):
        try:
            return f.decrypt(token)
        except InvalidToken as e:
            last_exc = e
            continue
        except Exception as e:
            last_exc = e
            continue

    # Legacy plaintext fallback (PNG/JPEG/GIF signature bytes)
    if token[:8] == b"\x89PNG\r\n\x1a\n" or token[:3] in (b"\xff\xd8\xff", b"GIF"):
        return token

    if isinstance(last_exc, InvalidToken):
        raise last_exc
    raise InvalidToken("Unable to decrypt signature token")
