from __future__ import annotations

from backend.comparison.models.document import CanonicalBlock


def merge_blocks(blocks: list[CanonicalBlock] | tuple[CanonicalBlock, ...]) -> tuple[str, str]:
    raw = "\n".join(block.original_text for block in blocks)
    normalized = "".join(block.compare_text or block.normalized_text for block in blocks)
    return raw, normalized
