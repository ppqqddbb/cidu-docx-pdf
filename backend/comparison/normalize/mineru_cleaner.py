from __future__ import annotations

import re
from html import unescape

from backend.comparison.config import ComparisonConfig
from backend.comparison.normalize.list_item import parse_list_item
from backend.comparison.normalize.normalizer import normalize_with_map
from backend.comparison.normalize.semantic_fact import semantic_fact_text

_HTML_TAG_RE = re.compile(r"<[^>]+>", re.IGNORECASE)
_MARKDOWN_TOKENS = ("**", "__", "`")


def clean_mineru_text_with_map(text: str, config: ComparisonConfig | None = None, *, block_type: str | None = None, raw_type: str | None = None) -> tuple[str, list[int]]:
    config = config or ComparisonConfig()
    raw_chars: list[str] = []
    raw_map: list[int] = []
    i = 0
    value = text or ""
    while i < len(value):
        if config.strip_html_formatting:
            match = _HTML_TAG_RE.match(value, i)
            if match:
                tag = match.group(0).lower()
                replacement = "\n" if tag.startswith("<br") or tag.startswith("</p") else ""
                for char in replacement:
                    raw_chars.append(char)
                    raw_map.append(i)
                i = match.end()
                continue
        if config.strip_markdown_formatting:
            if value[i] == "[":
                i += 1
                continue
            if value[i] == "]":
                destination = re.match(r"\]\([^)]*\)", value[i:])
                if destination:
                    i += len(destination.group(0))
                    continue
                i += 1
                continue
            token = next((token for token in _MARKDOWN_TOKENS if value.startswith(token, i)), None)
            if token is not None:
                i += len(token)
                continue
        raw_chars.append(value[i])
        raw_map.append(i)
        i += 1
    unescaped = unescape("".join(raw_chars))
    # html.unescape can collapse entities to one char. When that happens, fall back to
    # a conservative monotonic map by source position.
    if len(unescaped) == len(raw_chars):
        intermediate_map = raw_map
    else:
        intermediate_map = []
        cursor = 0
        for char in unescaped:
            intermediate_map.append(raw_map[min(cursor, len(raw_map) - 1)] if raw_map else 0)
            cursor += 1
    fact_text = semantic_fact_text(
        raw_type or "",
        unescaped,
        normalize_numeric=(
            config.normalize_numeric_format_for_matching
            and not config.report_numeric_format_change
        ),
    )
    if fact_text:
        compare_text, normalized_map = normalize_with_map(fact_text, config)
        return compare_text, [intermediate_map[index] for index in normalized_map if index < len(intermediate_map)]
    list_item = parse_list_item(unescaped, block_type=block_type)
    if config.strip_list_number_for_matching and list_item is not None:
        body = unescaped[list_item.body_start :]
        compare_text, normalized_map = normalize_with_map(body, config)
        return compare_text, [intermediate_map[list_item.body_start + index] for index in normalized_map if list_item.body_start + index < len(intermediate_map)]
    compare_text, normalized_map = normalize_with_map(unescaped, config)
    return compare_text, [intermediate_map[index] for index in normalized_map if index < len(intermediate_map)]
