from __future__ import annotations

from typing import Any

from backend.comparison.config import ComparisonConfig
from backend.comparison.models.document import BlockType, CanonicalBlock, CanonicalDocument, SourceType
from backend.comparison.normalize.mineru_cleaner import clean_mineru_text_with_map


class MinerUAdapter:
    def __init__(self, config: ComparisonConfig | None = None) -> None:
        self.config = config or ComparisonConfig()

    def to_canonical(self, payload: dict[str, Any], document_id: str) -> CanonicalDocument:
        blocks: list[CanonicalBlock] = []
        warnings: list[str] = []
        metadata = {
            "metadata": payload.get("metadata", {}),
            "extensions": payload.get("extensions", {}),
        }
        for source_index, block, page_index in self._iter_blocks(payload):
            raw_type = str(block.get("type") or block.get("block_type") or "unknown")
            block_type = self._block_type(raw_type)
            original_text = self._extract_text(block)
            if block_type == "unknown":
                warnings.append(f"unknown block type '{raw_type}' at page {page_index} block {source_index}")
            if not original_text and block_type not in {"image", "formula"}:
                continue
            normalized, offset_map = clean_mineru_text_with_map(original_text, self.config, block_type=block_type, raw_type=raw_type)
            source_type = self._source_type(block)
            blocks.append(
                CanonicalBlock(
                    id=f"{document_id}_b{len(blocks)}",
                    order_index=len(blocks),
                    type=block_type,
                    original_text=original_text,
                    normalized_text=normalized,
                    normalized_to_original_map=offset_map,
                    compare_text=normalized,
                    compare_to_original_map=offset_map,
                    page_index=page_index,
                    source_block_index=source_index,
                    bbox=block.get("bbox") or block.get("box"),
                    source_type=source_type,
                    metadata={"raw_type": raw_type, **{k: v for k, v in block.items() if k not in {"content"}}},
                )
            )
        return CanonicalDocument(document_id=document_id, source_type="mineru", blocks=blocks, metadata=metadata, warnings=warnings)

    def _iter_blocks(self, payload: dict[str, Any]):
        pages = payload.get("pages") or payload.get("pdf_info")
        if isinstance(pages, list):
            for page_pos, page in enumerate(pages):
                if not isinstance(page, dict):
                    continue
                page_index = self._safe_int(page.get("page_idx", page.get("page_no")), page_pos)
                block_list = page.get("blocks") or page.get("items") or page.get("para_blocks") or page.get("content")
                if isinstance(block_list, list):
                    for block_pos, block in enumerate(block_list):
                        if isinstance(block, dict):
                            yield block_pos, block, page_index
            return
        for key in ("blocks", "items", "content", "structured_content"):
            value = payload.get(key)
            if isinstance(value, list):
                for block_pos, block in enumerate(value):
                    if isinstance(block, dict):
                        yield block_pos, block, None

    def _extract_text(self, block: dict[str, Any]) -> str:
        content = block.get("content")
        if isinstance(content, str):
            return content
        if isinstance(block.get("text"), str):
            return str(block["text"])
        if isinstance(content, list):
            return "".join(self._extract_text(item) if isinstance(item, dict) else str(item) for item in content)
        parts: list[str] = []
        for key in ("lines", "spans", "items"):
            items = block.get(key)
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        text = item.get("text") or item.get("content")
                        if isinstance(text, str):
                            parts.append(text)
        return "\n".join(parts)

    def _block_type(self, raw_type: str) -> BlockType:
        value = raw_type.lower()
        if value in {"paragraph_title", "doc_title", "title", "heading"}:
            return "heading"
        if value in {"text", "paragraph"}:
            return "text"
        if value in {"list", "list_item", "index"}:
            return "list"
        if value in {"table", "table_body", "chart"}:
            return "table"
        if value in {"image", "figure"}:
            return "image"
        if value in {"formula", "equation", "equation_interline"}:
            return "formula"
        if value in {"header", "footer", "page_header", "page_footer", "page_number"}:
            return "text" if self.config.compare_page_auxiliary else "unknown"
        return "unknown"

    def _source_type(self, block: dict[str, Any]) -> SourceType:
        source = str(block.get("source_type") or block.get("source") or "").lower()
        if source in {"native", "ocr"}:
            return source  # type: ignore[return-value]
        if block.get("ocr_confidence") is not None:
            return "ocr"
        return "unknown"

    def _safe_int(self, value: Any, default: int | None) -> int | None:
        try:
            return int(value)
        except Exception:
            return default
