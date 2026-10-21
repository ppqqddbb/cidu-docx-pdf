from __future__ import annotations

from copy import copy

from backend.comparison.models.document import CanonicalBlock
from backend.comparison.alignment.key_value_matcher import parse_key_value
from backend.comparison.normalize.list_item import parse_list_item

_END_PUNCTUATION = tuple("。；;！？!?：:")


class LogicalUnitBuilder:
    def build(self, blocks: list[CanonicalBlock]) -> list[CanonicalBlock]:
        units: list[CanonicalBlock] = []
        for block in blocks:
            if units and _should_merge(units[-1], block):
                units[-1] = _merge(units[-1], block)
            else:
                units.append(block)
        return units


def _should_merge(left: CanonicalBlock, right: CanonicalBlock) -> bool:
    if left.type not in {"text", "paragraph"} or right.type not in {"text", "paragraph"}:
        return False
    if parse_list_item(left.original_text, block_type=left.type) or parse_list_item(right.original_text, block_type=right.type):
        return False
    if parse_key_value(left.compare_text or "") or parse_key_value(right.compare_text or ""):
        return False
    left_text = (left.compare_text or "").strip()
    right_text = (right.compare_text or "").strip()
    if not left_text or not right_text:
        return False
    return not left_text.endswith(_END_PUNCTUATION)


def _merge(left: CanonicalBlock, right: CanonicalBlock) -> CanonicalBlock:
    merged = copy(left)
    merged.id = f"{left.id}+{right.id}"
    merged.original_text = left.original_text + right.original_text
    merged.normalized_text = (left.normalized_text or "") + (right.normalized_text or "")
    merged.compare_text = (left.compare_text or "") + (right.compare_text or "")
    left_map = left.compare_to_original_map or left.normalized_to_original_map
    right_map = right.compare_to_original_map or right.normalized_to_original_map
    merged.compare_to_original_map = left_map + [len(left.original_text) + value for value in right_map]
    merged.normalized_to_original_map = merged.compare_to_original_map
    merged.metadata = {
        **left.metadata,
        "merged_block_ids": [*(left.metadata.get("merged_block_ids") or [left.id]), right.id],
    }
    return merged
