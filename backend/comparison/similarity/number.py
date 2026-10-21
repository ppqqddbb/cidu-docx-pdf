from __future__ import annotations

import re

NUMBER_PATTERN = re.compile(
    r"(?:GB/T\s*)?\d+(?:[./:-]\d+)*(?:\.\d+)?(?:%|MPa|kW|KW|℃|元|万元|年|月|日)?",
    re.IGNORECASE,
)


class NumberExtractor:
    def extract(self, text: str) -> list[str]:
        return [_normalize_number(match.group(0)) for match in NUMBER_PATTERN.finditer(text or "")]


def _normalize_number(value: str) -> str:
    suffix = ""
    raw = value
    while raw and not raw[-1].isdigit() and raw[-1] != ".":
        suffix = raw[-1] + suffix
        raw = raw[:-1]
    try:
        number = float(raw)
    except ValueError:
        return value
    rendered = str(int(number)) if number.is_integer() else str(number)
    return rendered + suffix
