from __future__ import annotations

from difflib import SequenceMatcher


def common_content_ratio(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    matcher = SequenceMatcher(None, left, right, autojunk=False)
    common = sum(block.size for block in matcher.get_matching_blocks())
    return common / max(1, min(len(left), len(right)))


def common_content_chars(left: str, right: str) -> int:
    if not left or not right:
        return 0
    matcher = SequenceMatcher(None, left, right, autojunk=False)
    return sum(block.size for block in matcher.get_matching_blocks())


def has_common_content(left: str, right: str, threshold: float) -> bool:
    if left == right:
        return True
    return common_content_ratio(left, right) >= threshold or common_content_chars(left, right) >= 6
