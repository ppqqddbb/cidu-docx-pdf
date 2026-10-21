from __future__ import annotations

from backend.comparison.models.diff import SourceRange
from backend.comparison.models.document import CanonicalBlock, CanonicalDocument
from backend.comparison.normalize.normalizer import normalized_original_span


class SourceMapper:
    def range_for(
        self,
        document: CanonicalDocument,
        blocks: list[CanonicalBlock],
        normalized_start: int | None,
        normalized_end: int | None,
    ) -> SourceRange:
        if not blocks:
            return SourceRange(document.document_id, [], None, None, None, None)
        if len(blocks) == 1:
            start, end = normalized_original_span(blocks[0].compare_to_original_map or blocks[0].normalized_to_original_map, normalized_start, normalized_end)
            return SourceRange(document.document_id, [blocks[0].id], blocks[0].page_index, start, end, blocks[0].bbox)
        return SourceRange(
            document.document_id,
            [block.id for block in blocks],
            blocks[0].page_index,
            None,
            None,
            blocks[0].bbox,
        )
