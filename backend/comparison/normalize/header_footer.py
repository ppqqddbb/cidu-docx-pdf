from __future__ import annotations

from collections import Counter

from backend.comparison.config import ComparisonConfig
from backend.comparison.models.document import CanonicalDocument


class HeaderFooterDetector:
    def __init__(self, config: ComparisonConfig | None = None) -> None:
        self.config = config or ComparisonConfig()

    def mark(self, document: CanonicalDocument) -> None:
        if not self.config.header_footer_enabled or self.config.compare_page_auxiliary:
            return
        pages = {b.page_index for b in document.blocks if b.page_index is not None}
        if len(pages) < 3:
            return
        texts = Counter(b.normalized_text for b in document.blocks if b.normalized_text and len(b.normalized_text) <= 40)
        repeated = {text for text, count in texts.items() if count >= max(2, len(pages) // 2)}
        for block in document.blocks:
            raw_type = str(block.metadata.get("raw_type", "")).lower()
            if raw_type in {"header", "footer", "page_header", "page_footer", "page_number"}:
                block.excluded = True
            elif block.normalized_text in repeated and _looks_like_page_aux(block.normalized_text):
                block.excluded = True


def _looks_like_page_aux(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ("第", "页", "page", "合同", "公司", "共"))
