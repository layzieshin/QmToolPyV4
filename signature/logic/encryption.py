from __future__ import annotations

import base64
import hashlib
import os
import platform
import uuid
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives import constant_time

try:
    # Provided by host application; fallback only for typing.
    from core.settings.logic.settings_manager import SettingsManager  # type: ignore
except Exception:
    SettingsManager = object  # type: ignore

_FEATURE_ID = "core_signature"
_SALT_KEY = "encryption_salt"
_KEY_CACHE: Optional[Fernet] = None

def _machine_fingerprint() -> bytes:
    """
    Stable machine-bound fingerprint to lock signature blobs to this machine.
    Avoids hardcoding secrets while hindering exfiltration.
    """
    parts = [platform.system(), platform.node(), platform.machine(), str(uuid.getnode())]
    return hashlib.sha256("::".join(parts).encode("utf-8")).digest()

def _derive_key(salt: bytes, fingerprint: bytes) -> bytes:
    """Derive a 32 byte key using Scrypt (interactive params)."""
    kdf = Scrypt(salt=salt + fingerprint[:16], length=32, n=2**14, r=8, p=1)
    raw = kdf.derive(fingerprint)
    return base64.urlsafe_b64encode(raw)

def _fernet(sm: "SettingsManager") -> Fernet:
    """Create/cache a Fernet key from app-stored salt + machine fingerprint."""
    global _KEY_CACHE
    if _KEY_CACHE is not None:
        return _KEY_CACHE
    salt_b64 = sm.get(_FEATURE_ID, _SALT_KEY, None)
    if not salt_b64:
        new = os.urandom(16)
        sm.set(_FEATURE_ID, _SALT_KEY, base64.b64encode(new).decode("ascii"))
        salt = new
    else:
        salt = base64.b64decode(salt_b64)
    _KEY_CACHE = Fernet(_derive_key(salt, _machine_fingerprint()))
    return _KEY_CACHE

def encrypt_bytes(sm: "SettingsManager", data: bytes) -> bytes:
    """Encrypt arbitrary bytes with module key."""
    return _fernet(sm).encrypt(data)

def decrypt_bytes(sm: "SettingsManager", token: bytes) -> bytes:
    """Decrypt bytes; raises if tampered or opened on another machine."""
    return _fernet(sm).decrypt(token)

def safe_compare_hash(a: str, b: str) -> bool:
    """Constant-time string compare (e.g., for hash equality checks)."""
    return constant_time.bytes_eq(a.encode("utf-8"), b.encode("utf-8"))
