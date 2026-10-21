from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape

_TAG_RE = re.compile(r"<[^>]+>")
_CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.IGNORECASE | re.DOTALL)
_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_KV_RE = re.compile(r"^\s*([^：:|]{1,30})[：:|]\s*(.*?)\s*$")


@dataclass(frozen=True)
class SemanticFact:
    key: str
    value: str


def semantic_fact_text(raw_type: str, text: str, *, normalize_numeric: bool = True) -> str | None:
    facts = extract_semantic_facts(raw_type, text)
    if not facts:
        return None
    return "|".join(
        f"{fact.key}:{_normalize_numeric_value(fact.value) if normalize_numeric else fact.value}"
        for fact in facts
    )


def extract_semantic_facts(raw_type: str, text: str) -> list[SemanticFact]:
    if raw_type.lower() == "table" or "<table" in (text or "").lower():
        return _extract_table_facts(text)
    fact = _extract_key_value_fact(text)
    return [fact] if fact else []


def _extract_table_facts(text: str) -> list[SemanticFact]:
    rows: list[list[str]] = []
    for row_match in _ROW_RE.finditer(text or ""):
        cells = [_clean_cell(cell) for cell in _CELL_RE.findall(row_match.group(1))]
        cells = [cell for cell in cells if cell]
        if cells:
            rows.append(cells)
    if len(rows) >= 2:
        header = rows[0]
        values = rows[1]
        return [SemanticFact(key, values[index]) for index, key in enumerate(header) if index < len(values) and key]
    if len(rows) == 1 and len(rows[0]) >= 2:
        return [SemanticFact(rows[0][i], rows[0][i + 1]) for i in range(0, len(rows[0]) - 1, 2)]
    return []


def _extract_key_value_fact(text: str) -> SemanticFact | None:
    match = _KV_RE.match(text or "")
    if not match:
        return None
    return SemanticFact(match.group(1).strip(), match.group(2).strip())


def _clean_cell(value: str) -> str:
    return unescape(_TAG_RE.sub("", value or "")).strip()


def _normalize_numeric_value(value: str) -> str:
    raw_value = value or ""
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)(\D*)\s*", raw_value)
    if not match:
        return raw_value
    try:
        num = float(match.group(1))
    except ValueError:
        return raw_value
    rendered = str(int(num)) if num.is_integer() else str(num)
    return rendered + match.group(2)
