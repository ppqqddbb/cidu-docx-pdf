from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

BlockType = Literal["heading", "paragraph", "text", "list", "table", "image", "formula", "unknown"]
SourceType = Literal["native", "ocr", "unknown"]


@dataclass
class CanonicalBlock:
    id: str
    order_index: int
    type: BlockType
    original_text: str
    normalized_text: str
    normalized_to_original_map: list[int]
    compare_text: str | None = None
    compare_to_original_map: list[int] | None = None
    page_index: int | None = None
    source_block_index: int | None = None
    bbox: Any = None
    source_type: SourceType = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)
    excluded: bool = False

    def __post_init__(self) -> None:
        if self.compare_text is None:
            self.compare_text = self.normalized_text
        if self.compare_to_original_map is None:
            self.compare_to_original_map = self.normalized_to_original_map


@dataclass
class CanonicalDocument:
    document_id: str
    source_type: str
    blocks: list[CanonicalBlock]
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def body_blocks(self) -> list[CanonicalBlock]:
        return [b for b in self.blocks if not b.excluded and b.type in {"heading", "paragraph", "text", "list", "table"} and b.compare_text]
