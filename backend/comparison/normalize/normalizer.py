from __future__ import annotations

import re
import unicodedata

from backend.comparison.config import ComparisonConfig

_ZERO_WIDTH = {"\u200b", "\u200c", "\u200d", "\ufeff"}
_SPACE_RE = re.compile(r"\s+")


def normalize_with_map(text: str, config: ComparisonConfig | None = None) -> tuple[str, list[int]]:
    config = config or ComparisonConfig()
    normalized_chars: list[str] = []
    index_map: list[int] = []
    pending_space_index: int | None = None

    for original_index, char in enumerate(text or ""):
        if char in _ZERO_WIDTH:
            continue
        char = "\n" if char in {"\r", "\n"} else char
        char = " " if char in {"\t", "\u00a0", "\u3000"} else char
        folded = unicodedata.normalize("NFKC", char)
        for folded_char in folded:
            if folded_char in _ZERO_WIDTH:
                continue
            if folded_char.isspace():
                if config.compare_whitespace:
                    pending_space_index = original_index
                continue
            if pending_space_index is not None and config.compare_whitespace and normalized_chars:
                normalized_chars.append(" ")
                index_map.append(pending_space_index)
            pending_space_index = None
            if not config.compare_punctuation and unicodedata.category(folded_char).startswith("P"):
                continue
            normalized_chars.append(folded_char)
            index_map.append(original_index)

    value = "".join(normalized_chars)
    if config.compare_whitespace:
        value = _SPACE_RE.sub(" ", value).strip()
    return value, index_map


def normalized_original_span(index_map: list[int], start: int | None, end: int | None) -> tuple[int | None, int | None]:
    if start is None or end is None or start >= end or not index_map:
        return None, None
    bounded_start = min(max(start, 0), len(index_map) - 1)
    bounded_end = min(max(end - 1, 0), len(index_map) - 1)
    return index_map[bounded_start], index_map[bounded_end] + 1
