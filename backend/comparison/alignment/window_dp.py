from __future__ import annotations

import re
from math import inf

from backend.comparison.alignment.block_merger import merge_blocks
from backend.comparison.config import ComparisonConfig
from backend.comparison.models.alignment import Alignment, Region
from backend.comparison.models.document import CanonicalBlock
from backend.comparison.similarity.engine import SimilarityEngine


class WindowDPAligner:
    def __init__(self, config: ComparisonConfig | None = None, similarity: SimilarityEngine | None = None) -> None:
        self.config = config or ComparisonConfig()
        self.similarity = similarity or SimilarityEngine(self.config)

    def align_region(self, old_blocks: list[CanonicalBlock], new_blocks: list[CanonicalBlock], region: Region) -> list[Alignment]:
        old = old_blocks[region.old_start : region.old_end]
        new = new_blocks[region.new_start : region.new_end]
        n, m = len(old), len(new)
        if n == 1 and m == 1 and (old[0].compare_text or "") == (new[0].compare_text or ""):
            return [Alignment("MATCH", (region.old_start,), (region.new_start,), 1.0, "MATCH_1_1")]
        dp = [[inf] * (m + 1) for _ in range(n + 1)]
        back: list[list[tuple | None]] = [[None] * (m + 1) for _ in range(n + 1)]
        dp[0][0] = 0.0
        for i in range(n + 1):
            for j in range(m + 1):
                if dp[i][j] == inf:
                    continue
                if not self._cell_allowed(i, j, n, m, region):
                    continue
                if i < n and dp[i][j] + self.config.delete_cost < dp[i + 1][j]:
                    dp[i + 1][j] = dp[i][j] + self.config.delete_cost
                    back[i + 1][j] = ("DELETE", 1, 0, None, None)
                if j < m and dp[i][j] + self.config.insert_cost < dp[i][j + 1]:
                    dp[i][j + 1] = dp[i][j] + self.config.insert_cost
                    back[i][j + 1] = ("INSERT", 0, 1, None, None)
                for old_count in range(1, min(self.config.max_merge_blocks, n - i) + 1):
                    for new_count in range(1, min(self.config.max_merge_blocks, m - j) + 1):
                        if old_count > 1 and new_count > 1:
                            continue
                        if old_count > 1 and _crosses_clause_boundaries(old[i : i + old_count]):
                            continue
                        if new_count > 1 and _crosses_clause_boundaries(new[j : j + new_count]):
                            continue
                        _, old_text = merge_blocks(old[i : i + old_count])
                        _, new_text = merge_blocks(new[j : j + new_count])
                        old_pos = (region.old_start + i) / max(1, len(old_blocks))
                        new_pos = (region.new_start + j) / max(1, len(new_blocks))
                        sim = self.similarity.score(old_text, new_text, old_pos, new_pos)
                        if sim.score < self.config.match_threshold:
                            continue
                        penalty = self.config.merge_penalty * (old_count + new_count - 2)
                        cost = dp[i][j] + 1.0 - sim.score + penalty
                        if cost < dp[i + old_count][j + new_count]:
                            dp[i + old_count][j + new_count] = cost
                            back[i + old_count][j + new_count] = ("MATCH", old_count, new_count, sim.score, f"MATCH_{old_count}_{new_count}")
        alignments: list[Alignment] = []
        i, j = n, m
        while i > 0 or j > 0:
            step = back[i][j]
            if step is None:
                step = ("DELETE", 1, 0, None, None) if i > 0 else ("INSERT", 0, 1, None, None)
            op, old_count, new_count, score, alignment_type = step
            old_start = i - old_count
            new_start = j - new_count
            old_indices = tuple(range(region.old_start + old_start, region.old_start + i))
            new_indices = tuple(range(region.new_start + new_start, region.new_start + j))
            alignments.append(Alignment(op, old_indices, new_indices, score, alignment_type))
            i, j = old_start, new_start
        return _order_gaps(list(reversed(alignments)))

    def _cell_allowed(self, i: int, j: int, n: int, m: int, region: Region) -> bool:
        if n * m <= self.config.dp_full_matrix_limit:
            return True
        # The band follows the index displacement established by the surrounding
        # anchors.  Interpolation also handles sections whose length changed.
        if n == 0:
            expected = float(m)
        else:
            left_offset = (
                region.left_anchor.new_index - region.left_anchor.old_index
                if region.left_anchor is not None
                else region.new_start - region.old_start
            )
            right_offset = (
                region.right_anchor.new_index - region.right_anchor.old_index
                if region.right_anchor is not None
                else (region.new_end - region.old_end)
            )
            progress = i / n
            offset = left_offset + (right_offset - left_offset) * progress
            expected_global_new = (region.old_start + i) + offset
            expected = expected_global_new - region.new_start
        width = max(self.config.adaptive_dp_band_width, abs(m - n) + self.config.max_merge_blocks)
        return abs(j - expected) <= width or (i == n and j == m)


def _order_gaps(alignments: list[Alignment]) -> list[Alignment]:
    ordered: list[Alignment] = []
    i = 0
    while i < len(alignments):
        current = alignments[i]
        nxt = alignments[i + 1] if i + 1 < len(alignments) else None
        if nxt and {current.operation, nxt.operation} == {"DELETE", "INSERT"}:
            delete = current if current.operation == "DELETE" else nxt
            insert = current if current.operation == "INSERT" else nxt
            ordered.extend([delete, insert])
            i += 2
        else:
            ordered.append(current)
            i += 1
    return ordered


def _crosses_clause_boundaries(blocks: list[CanonicalBlock]) -> bool:
    prefixes = []
    for block in blocks:
        # compare_text normally has list/clause numbering removed, so inspect
        # the source text first.  Otherwise a 1:N transition can silently
        # consume a newly inserted numbered clause together with the real
        # renumbered counterpart.
        match = re.match(r"^\s*(\d+(?:\.\d+)+)[.、)]?", block.original_text or block.compare_text or "")
        if match:
            prefixes.append(match.group(1))
    return len(set(prefixes)) > 1
