from __future__ import annotations

from backend.comparison.models.alignment import Anchor, Region


class RegionBuilder:
    def build(self, anchors: list[Anchor], old_count: int, new_count: int) -> list[Region]:
        regions: list[Region] = []
        prev_old = 0
        prev_new = 0
        left_anchor: Anchor | None = None
        for anchor in anchors:
            if prev_old < anchor.old_index or prev_new < anchor.new_index:
                regions.append(Region(prev_old, anchor.old_index, prev_new, anchor.new_index, left_anchor, anchor))
            regions.append(Region(anchor.old_index, anchor.old_index + 1, anchor.new_index, anchor.new_index + 1, anchor, anchor))
            prev_old = anchor.old_index + 1
            prev_new = anchor.new_index + 1
            left_anchor = anchor
        if prev_old < old_count or prev_new < new_count:
            regions.append(Region(prev_old, old_count, prev_new, new_count, left_anchor, None))
        return regions
