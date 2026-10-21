from __future__ import annotations

from collections import Counter

from backend.comparison.config import ComparisonConfig
from backend.comparison.models.document import CanonicalDocument


class QualityGate:
    def __init__(self, config: ComparisonConfig | None = None) -> None:
        self.config = config or ComparisonConfig()

    def evaluate(self, document: CanonicalDocument) -> dict:
        blocks = document.blocks
        text_blocks = [b for b in blocks if b.type in {"heading", "paragraph", "text", "list"}]
        total_chars = sum(len(b.normalized_text) for b in text_blocks)
        empty_blocks = sum(1 for b in blocks if not b.normalized_text)
        short_blocks = sum(1 for b in text_blocks if 0 < len(b.normalized_text) <= self.config.short_block_chars)
        page_indices = {b.page_index for b in blocks if b.page_index is not None}
        pages_with_text = {b.page_index for b in text_blocks if b.page_index is not None and b.normalized_text}
        duplicates = Counter(b.normalized_text for b in text_blocks if b.normalized_text)
        duplicate_blocks = sum(count for count in duplicates.values() if count > 1)
        invalid_chars = sum(1 for b in text_blocks for ch in b.original_text if ord(ch) in range(0, 9))
        ocr_blocks = sum(1 for b in blocks if b.source_type == "ocr")
        warnings = list(document.warnings)
        pages_without_text_ratio = 0.0
        if page_indices:
            pages_without_text_ratio = (len(page_indices - pages_with_text)) / len(page_indices)
        if total_chars < self.config.min_quality_chars and len(page_indices) > 1:
            warnings.append("very low extracted text volume")
        if pages_without_text_ratio >= self.config.pages_without_text_warning_ratio and len(page_indices) > 1:
            warnings.append("many pages have no text")
        score = 1.0
        score -= min(0.35, pages_without_text_ratio * 0.35)
        score -= min(0.25, (empty_blocks / max(1, len(blocks))) * 0.25)
        score -= min(0.20, (duplicate_blocks / max(1, len(text_blocks))) * 0.20)
        return {
            "total_blocks": len(blocks),
            "text_blocks": len(text_blocks),
            "empty_blocks": empty_blocks,
            "total_chars": total_chars,
            "avg_block_length": total_chars / max(1, len(text_blocks)),
            "short_block_ratio": short_blocks / max(1, len(text_blocks)),
            "duplicate_block_ratio": duplicate_blocks / max(1, len(text_blocks)),
            "invalid_char_ratio": invalid_chars / max(1, sum(len(b.original_text) for b in text_blocks)),
            "ocr_block_ratio": ocr_blocks / max(1, len(blocks)),
            "pages_without_text_ratio": pages_without_text_ratio,
            "quality_score": max(0.0, round(score, 4)),
            "quality_warnings": warnings,
        }
