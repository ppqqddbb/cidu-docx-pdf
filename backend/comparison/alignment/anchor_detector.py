from __future__ import annotations

import re
from collections import Counter, defaultdict

from backend.comparison.config import ComparisonConfig
from backend.comparison.models.alignment import Anchor
from backend.comparison.models.document import CanonicalBlock
from backend.comparison.normalize.list_item import parse_list_item


class AnchorDetector:
    def __init__(self, config: ComparisonConfig | None = None) -> None:
        self.config = config or ComparisonConfig()

    def exact_unique(self, old_blocks: list[CanonicalBlock], new_blocks: list[CanonicalBlock]) -> list[Anchor]:
        if not self.config.exact_anchor_enabled:
            return []
        old_counter = Counter((b.compare_text or "") for b in old_blocks if len(b.compare_text or "") >= self.config.min_anchor_chars)
        new_counter = Counter((b.compare_text or "") for b in new_blocks if len(b.compare_text or "") >= self.config.min_anchor_chars)
        old_positions: dict[str, list[int]] = defaultdict(list)
        new_positions: dict[str, list[int]] = defaultdict(list)
        for index, block in enumerate(old_blocks):
            old_positions[block.compare_text or ""].append(index)
        for index, block in enumerate(new_blocks):
            new_positions[block.compare_text or ""].append(index)
        anchors: list[Anchor] = []
        for text, old_count in old_counter.items():
            if old_count == 1 and new_counter.get(text) == 1:
                old_index = old_positions[text][0]
                new_index = new_positions[text][0]
                anchors.append(Anchor(old_index, new_index, 1.0, "exact", min(len(text), 120)))
        return anchors

    def exact_body(self, old_blocks: list[CanonicalBlock], new_blocks: list[CanonicalBlock]) -> list[Anchor]:
        """Return exact anchors for list bodies and section headings.

        List numbering is presentation structure, not business content.  The adapter
        already exposes the normalized body as ``compare_text``; this method gives
        exact body matches enough weight to establish the shifted index chain before
        the general DP runs.
        """
        old_keys = _anchor_keys(old_blocks)
        new_keys = _anchor_keys(new_blocks)
        old_counter = Counter(key for key in old_keys if key is not None)
        new_counter = Counter(key for key in new_keys if key is not None)
        new_positions = {key: index for index, key in enumerate(new_keys) if key is not None}
        anchors: list[Anchor] = []
        for old_index, key in enumerate(old_keys):
            if key is None or old_counter[key] != 1 or new_counter.get(key) != 1:
                continue
            kind, _section, text = key
            minimum = self.config.min_list_body_anchor_chars if kind == "list_body" else self.config.min_section_anchor_chars
            if len(text) < minimum:
                continue
            weight = min(len(text), 120) + (80 if kind == "section" else 40)
            anchors.append(Anchor(old_index, new_positions[key], 1.0, f"exact_{kind}", weight))
        return anchors

    def exact_clause_body(self, old_blocks: list[CanonicalBlock], new_blocks: list[CanonicalBlock]) -> list[Anchor]:
        """Anchor renumbered hierarchical clauses by their unchanged body text."""
        old_bodies = [_clause_body(block.compare_text or "") for block in old_blocks]
        new_bodies = [_clause_body(block.compare_text or "") for block in new_blocks]
        old_counter = Counter(body for body in old_bodies if len(body) >= self.config.min_anchor_chars)
        new_counter = Counter(body for body in new_bodies if len(body) >= self.config.min_anchor_chars)
        new_positions = {body: index for index, body in enumerate(new_bodies) if body}
        anchors: list[Anchor] = []
        for old_index, body in enumerate(old_bodies):
            if not body or old_counter.get(body) != 1 or new_counter.get(body) != 1:
                continue
            anchors.append(Anchor(old_index, new_positions[body], 1.0, "exact_clause_body", min(len(body), 120) + 60))
        return anchors


def _anchor_keys(blocks: list[CanonicalBlock]) -> list[tuple[str, str, str] | None]:
    keys: list[tuple[str, str, str] | None] = []
    parent_section = "__document__"
    section = "__root__"
    for block in blocks:
        text = block.compare_text or ""
        if not text:
            keys.append(None)
            continue
        if block.type == "heading" or _looks_like_section_heading(block.original_text):
            identity = _section_identity(text)
            if _looks_like_part_heading(text):
                parent_section = identity
                section = identity
                keys.append(("section", "__document__", identity))
            else:
                section = f"{parent_section}/{identity}"
                keys.append(("section", parent_section, identity))
            continue
        list_item = parse_list_item(block.original_text, block_type=block.type)
        if list_item is not None:
            keys.append(("list_body", section, text))
            continue
        keys.append(None)
    return keys


def _looks_like_section_heading(text: str) -> bool:
    value = (text or "").lstrip()
    if value.startswith("第") and any(marker in value[:12] for marker in ("条", "章", "节", "部分")):
        return True
    return False


def _section_identity(text: str) -> str:
    value = re.sub(r"\s+", "", text or "")
    value = re.sub(r"^第?[一二三四五六七八九十百零〇\d]+(?:条|节|章|部分)", "", value)
    value = re.sub(r"^\d+(?:\.\d+)*[.、)]?", "", value)
    return value or re.sub(r"\s+", "", text or "")


def _looks_like_part_heading(text: str) -> bool:
    value = re.sub(r"\s+", "", text or "")
    return bool(re.match(r"^第?[一二三四五六七八九十百零〇\d]+部分", value))


def _clause_body(text: str) -> str:
    match = re.match(r"^\s*\d+(?:\.\d+)+[.、)]?\s*(.+)$", text or "")
    return match.group(1).strip() if match else ""
