from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from .signature_enums import LabelPosition, OutputNamingMode, AdminPasswordPolicy
from .label_offsets import LabelOffsets

@dataclass
class SignatureConfig:
    """
    User-scope configuration persisted via SettingsManager under feature id 'core_signature'.
    Note: admin_password_policy is global (non user-specific).
    """
    # Drawing / labels
    stroke_width: int = 3
    embed_name: bool = True
    embed_date: bool = True
    name_position: LabelPosition = LabelPosition.ABOVE
    date_position: LabelPosition = LabelPosition.BELOW
    date_format: str = "%Y-%m-%d %H:%M"
    label_offsets: LabelOffsets = field(default_factory=LabelOffsets)

    # NEW: color for name/date labels (hex)
    label_color: str = "#000000"  # default: black

    # Output naming
    naming_mode: OutputNamingMode = OutputNamingMode.DEFAULT_SUFFIX
    external_strategy_id: Optional[str] = None

    # Security
    user_pwd_required: bool = True
    admin_password_policy: AdminPasswordPolicy = AdminPasswordPolicy.USER_SPECIFIC
