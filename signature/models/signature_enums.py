# signature/models/signature_enums.py
from __future__ import annotations
from enum import Enum


class LabelPosition(str, Enum):
    """Placement of a label relative to the signature block."""
    ABOVE = "above"
    BELOW = "below"
    OFF   = "off"     # NEW: do not render this label


class OutputNamingMode(str, Enum):
    DEFAULT_SUFFIX = "default_suffix"
    EXTERNAL_STRATEGY = "external_strategy"


class AdminPasswordPolicy(str, Enum):
    ALWAYS = "always"
    NEVER = "never"
    USER_SPECIFIC = "user_specific"
