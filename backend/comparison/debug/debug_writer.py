from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from backend.comparison.config import ComparisonConfig


class DebugWriter:
    def __init__(self, config: ComparisonConfig) -> None:
        self.enabled = config.debug_enabled
        self.root = config.debug_dir or Path("debug")
        if self.enabled:
            self.root.mkdir(parents=True, exist_ok=True)

    def write(self, name: str, value: Any) -> None:
        if not self.enabled:
            return
        path = self.root / name
        path.write_text(json.dumps(_jsonable(value), ensure_ascii=False, indent=2), encoding="utf-8")


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return value
