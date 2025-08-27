# signature/models/signature_config.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from .signature_enums import LabelPosition, OutputNamingMode, AdminPasswordPolicy
from .label_offsets import LabelOffsets

@dataclass
class SignatureConfig:
    """
    Persisted (user-scoped) configuration under feature id 'core_signature'.
    Hinweis:
      - admin_password_policy ist global (nicht user-spezifisch).
    """
    # Zeichen-/Label-Optionen
    stroke_width: int = 3
    embed_name: bool = True
    embed_date: bool = True
    name_position: LabelPosition = LabelPosition.ABOVE
    date_position: LabelPosition = LabelPosition.BELOW
    date_format: str = "%Y-%m-%d %H:%M"
    label_offsets: LabelOffsets = field(default_factory=LabelOffsets)

    # NEU: Farbe & Schriftgrößen (werden in Vorschau + finalem PDF genutzt)
    label_color: str = "#000000"   # Hex (#000 / #000000)
    name_font_size: int = 12       # pt
    date_font_size: int = 12       # pt

    # Ausgabe-Benennung
    naming_mode: OutputNamingMode = OutputNamingMode.DEFAULT_SUFFIX
    external_strategy_id: Optional[str] = None

    # Sicherheit / Policy
    user_pwd_required: bool = True
    admin_password_policy: AdminPasswordPolicy = AdminPasswordPolicy.USER_SPECIFIC
