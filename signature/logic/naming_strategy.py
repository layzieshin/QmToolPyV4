from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Protocol, Optional

@dataclass(frozen=True)
class NamingContext:
    input_path: str
    user_id: Optional[str]
    reason: Optional[str]

class NamingStrategy(Protocol):
    def strategy_id(self) -> str: ...
    def propose_output_path(self, ctx: NamingContext) -> str: ...

class DefaultSuffixStrategy:
    """Default: file.pdf -> file_signed.pdf"""
    def strategy_id(self) -> str:
        return "default_suffix"
    def propose_output_path(self, ctx: NamingContext) -> str:
        root, ext = os.path.splitext(ctx.input_path)
        if ext.lower() != ".pdf":
            ext = ".pdf"
        return f"{root}_signed{ext}"
