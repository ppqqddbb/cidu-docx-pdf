from __future__ import annotations

from backend.comparison.diff.rescue import DiffRescue


class LargeReplaceRefiner(DiffRescue):
    """V1 refinement delegates adjacent delete/insert rescue to character diff later."""
