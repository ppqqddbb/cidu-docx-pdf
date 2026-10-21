from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

DiffType = Literal["EQUAL", "INSERT", "DELETE"]


@dataclass
class DiffOp:
    type: DiffType
    text: str
    old_start: int | None = None
    old_end: int | None = None
    new_start: int | None = None
    new_end: int | None = None


@dataclass
class SourceRange:
    document_id: str
    block_ids: list[str]
    page_index: int | None
    start_offset: int | None
    end_offset: int | None
    bbox: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "block_ids": self.block_ids,
            "page_index": self.page_index,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "bbox": self.bbox,
        }


@dataclass
class Change:
    id: str
    type: Literal["INSERT", "DELETE"]
    text: str
    old: SourceRange
    new: SourceRange
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "text": self.text,
            "old": self.old.to_dict(),
            "new": self.new.to_dict(),
            "confidence": self.confidence,
            "metadata": self.metadata,
        }
