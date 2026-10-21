from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AlignmentKind = Literal["MATCH", "INSERT", "DELETE"]


@dataclass(frozen=True)
class Anchor:
    old_index: int
    new_index: int
    score: float
    anchor_type: str
    weight: float


@dataclass(frozen=True)
class Region:
    old_start: int
    old_end: int
    new_start: int
    new_end: int
    left_anchor: Anchor | None = None
    right_anchor: Anchor | None = None


@dataclass(frozen=True)
class Alignment:
    operation: AlignmentKind
    old_indices: tuple[int, ...]
    new_indices: tuple[int, ...]
    score: float | None = None
    alignment_type: str | None = None
