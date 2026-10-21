from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class StructuredLoader:
    def load(self, value: dict[str, Any] | str | Path) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        path = Path(value)
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("structured_content must be a JSON object")
        return data
