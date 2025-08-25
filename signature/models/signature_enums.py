from __future__ import annotations
from enum import Enum

class LabelPosition(str, Enum):
    """Placement of a label relative to the signature image."""
    ABOVE = "above"
    BELOW = "below"

class OutputNamingMode(str, Enum):
    """How the output PDF file name is chosen."""
    DEFAULT_SUFFIX = "default_suffix"          # <file>_signed.pdf
    EXTERNAL_STRATEGY = "external_strategy"    # via external registry

class AdminPasswordPolicy(str, Enum):
    """Global admin override for password requirement."""
    ALWAYS = "always"
    NEVER = "never"
    USER_SPECIFIC = "user_specific"
