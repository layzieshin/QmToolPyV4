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
    """Default signature output strategy.

    Phase 4 behavior:
    - During workflow signing rounds, we MUST NOT append '_signed' to filenames.
    - We output into a temporary working file in the same directory (no '_signed'),
      so the caller (workflow) can copy the result into the canonical lifecycle PDF path.
    """

    def strategy_id(self) -> str:
        # Keep ID stable to avoid breaking configuration.
        return "default_suffix"

    def propose_output_path(self, ctx: NamingContext) -> str:
        root, ext = os.path.splitext(ctx.input_path)
        if ext.lower() != ".pdf":
            ext = ".pdf"

        # Create a temporary working output path in the same directory.
        # No '_signed' suffix here by design.
        base = f"{root}_sig{ext}"
        if not os.path.exists(base):
            return base

        # Ensure uniqueness if file exists.
        for i in range(2, 1000):
            candidate = f"{root}_sig{i}{ext}"
            if not os.path.exists(candidate):
                return candidate

        # Fallback (extremely unlikely): overwrite the first one.
        return base
