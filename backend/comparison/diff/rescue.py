from __future__ import annotations

from backend.comparison.config import ComparisonConfig
from backend.comparison.alignment.key_value_matcher import same_key
from backend.comparison.diff.common_content import has_common_content
from backend.comparison.models.alignment import Alignment
from backend.comparison.models.document import CanonicalBlock
from backend.comparison.similarity.engine import SimilarityEngine


class DiffRescue:
    def __init__(self, config: ComparisonConfig | None = None, similarity: SimilarityEngine | None = None) -> None:
        self.config = config or ComparisonConfig()
        self.similarity = similarity or SimilarityEngine(self.config)

    def rescue(self, alignments: list[Alignment], old_blocks: list[CanonicalBlock], new_blocks: list[CanonicalBlock]) -> list[Alignment]:
        rescued: list[Alignment] = []
        i = 0
        while i < len(alignments):
            current = alignments[i]
            nxt = alignments[i + 1] if i + 1 < len(alignments) else None
            if nxt and current.operation == "DELETE" and nxt.operation == "INSERT":
                old_text = "".join(old_blocks[idx].compare_text or "" for idx in current.old_indices)
                new_text = "".join(new_blocks[idx].compare_text or "" for idx in nxt.new_indices)
                sim = self.similarity.score(old_text, new_text)
                if (
                    same_key(old_text, new_text)
                    or has_common_content(old_text, new_text, self.config.common_content_threshold)
                    or sim.score >= self.config.replace_rescue_threshold
                ):
                    rescued.append(Alignment("MATCH", current.old_indices, nxt.new_indices, sim.score, "RESCUED_REPLACE"))
                    i += 2
                    continue
            rescued.append(current)
            i += 1
        return rescued
