from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from difflib import SequenceMatcher

from backend.comparison.config import ComparisonConfig
from backend.comparison.similarity.ngram import dice_similarity
from backend.comparison.similarity.number import NumberExtractor


@dataclass(frozen=True)
class SimilarityScore:
    score: float
    char_similarity: float
    ngram_similarity: float
    number_similarity: float
    length_similarity: float
    position_similarity: float


class SimilarityEngine:
    def __init__(self, config: ComparisonConfig | None = None) -> None:
        self.config = config or ComparisonConfig()
        self.number_extractor = NumberExtractor()

    def score(self, old_text: str, new_text: str, old_pos: float = 0.0, new_pos: float = 0.0) -> SimilarityScore:
        return self._score_cached(old_text, new_text, round(old_pos, 4), round(new_pos, 4))

    @lru_cache(maxsize=20000)
    def _score_cached(self, old_text: str, new_text: str, old_pos: float, new_pos: float) -> SimilarityScore:
        char = SequenceMatcher(None, old_text, new_text, autojunk=False).ratio()
        ngram = (dice_similarity(old_text, new_text, 3) + dice_similarity(old_text, new_text, 4)) / 2
        nums_old = self.number_extractor.extract(old_text)
        nums_new = self.number_extractor.extract(new_text)
        if not nums_old and not nums_new:
            number = 1.0
        else:
            a, b = set(nums_old), set(nums_new)
            number = len(a & b) / max(1, len(a | b))
        length = min(len(old_text), len(new_text)) / max(1, max(len(old_text), len(new_text)))
        position = max(0.0, 1.0 - abs(old_pos - new_pos))
        score = (
            self.config.char_weight * char
            + self.config.ngram_weight * ngram
            + self.config.number_weight * number
            + self.config.length_weight * length
            + self.config.position_weight * position
        )
        return SimilarityScore(round(score, 6), char, ngram, number, length, position)
