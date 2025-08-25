from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class SignaturePlacement:
    """
    Absolute placement on a PDF page (points; 1 pt = 1/72 inch), origin bottom-left.
    """
    page_index: int = 0
    x: float = 72 * 4           # 4 inches from left
    y: float = 72 * 1.5         # 1.5 inches from bottom
    target_width: float = 72 * 2.5  # width of signature image; height keeps aspect
