from __future__ import annotations

import re
from dataclasses import dataclass

_KEY_RE = re.compile(r"^(.{1,30}?)[：:](.*)$")
_KNOWN_KEYS = {
    "合同编号",
    "买方",
    "卖方",
    "甲方",
    "乙方",
    "签署日期",
    "签订日期",
    "签订地点",
    "项目名称",
    "工程名称",
    "设备名称",
    "合同名称",
    "联系人",
    "地址",
    "电话",
}


@dataclass(frozen=True)
class KeyValue:
    key: str
    value: str
    value_start: int


def parse_key_value(text: str) -> KeyValue | None:
    compact = (text or "").strip()
    match = _KEY_RE.match(compact)
    if not match:
        return None
    key = match.group(1).strip()
    value = match.group(2).strip()
    normalized_key = key.rstrip("：:")
    if normalized_key in _KNOWN_KEYS or len(normalized_key) <= 8:
        return KeyValue(normalized_key, value, match.start(2) + len(match.group(2)) - len(match.group(2).lstrip()))
    return None


def same_key(left: str, right: str) -> bool:
    old = parse_key_value(left)
    new = parse_key_value(right)
    return bool(old and new and old.key == new.key)
