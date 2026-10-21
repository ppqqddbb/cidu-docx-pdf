from __future__ import annotations

import re
from dataclasses import dataclass

_LIST_MARKER_RE = re.compile(
    r"^\s*(?P<prefix>(?:\((?P<num1>\d{1,3})\)|（(?P<num2>\d{1,3})）|(?P<num3>\d{1,3})[.、)]))\s*(?P<body>.+)$"
)


@dataclass(frozen=True)
class ListItemParts:
    list_number: str
    list_prefix: str
    body_text: str
    body_start: int


def parse_list_item(text: str, *, block_type: str | None = None) -> ListItemParts | None:
    value = text or ""
    if block_type == "heading" or value.lstrip().startswith("第"):
        return None
    match = _LIST_MARKER_RE.match(value)
    if not match:
        return None
    number = match.group("num1") or match.group("num2") or match.group("num3") or ""
    body = match.group("body")
    if not body.strip():
        return None
    return ListItemParts(
        list_number=number,
        list_prefix=match.group("prefix"),
        body_text=body.strip(),
        body_start=match.start("body") + len(body) - len(body.lstrip()),
    )
