from __future__ import annotations
from dataclasses import dataclass

@dataclass
class LabelOffsets:
    """
    Offsets in PDF points (1pt = 1/72 inch).
    All offsets are measured relative to the signature image:
      - 'above' offsets are measured UP from the top edge of the signature
      - 'below' offsets are measured DOWN from the bottom edge of the signature
      - x_offset shifts labels horizontally from the left edge of the signature
    """
    name_above: float = 6.0
    name_below: float = 12.0
    date_above: float = 18.0
    date_below: float = 24.0
    x_offset: float = 0.0
