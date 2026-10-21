from __future__ import annotations

import logging
import time
from dataclasses import asdict
from typing import Any
from uuid import uuid4

from backend.comparison.alignment.anchor_detector import AnchorDetector
from backend.comparison.alignment.block_merger import merge_blocks
from backend.comparison.alignment.key_value_matcher import parse_key_value
from backend.comparison.alignment.logical_unit import LogicalUnitBuilder
from backend.comparison.normalize.semantic_fact import SemanticFact
from backend.comparison.alignment.monotonic import MonotonicAnchorSelector
from backend.comparison.alignment.region_builder import RegionBuilder
from backend.comparison.alignment.window_dp import WindowDPAligner
from backend.comparison.config import ComparisonConfig
from backend.comparison.debug.debug_writer import DebugWriter
from backend.comparison.diff.char_diff import char_diff
from backend.comparison.diff.coalescer import DiffCoalescer
from backend.comparison.diff.replace_refiner import LargeReplaceRefiner
from backend.comparison.loader.mineru_adapter import MinerUAdapter
from backend.comparison.loader.markdown_loader import MarkdownLoader
from backend.comparison.loader.structured_loader import StructuredLoader
from backend.comparison.mapping.source_mapper import SourceMapper
from backend.comparison.models.alignment import Alignment
from backend.comparison.models.diff import Change, DiffOp
from backend.comparison.models.document import CanonicalBlock, CanonicalDocument
from backend.comparison.normalize.header_footer import HeaderFooterDetector
from backend.comparison.quality.quality_gate import QualityGate
from backend.comparison.similarity.engine import SimilarityEngine

logger = logging.getLogger(__name__)


def compare_documents(
    old_structured_content: dict[str, Any] | str,
    new_structured_content: dict[str, Any] | str,
    config: ComparisonConfig | None = None,
) -> dict[str, Any]:
    return ComparisonService(config).compare_documents(old_structured_content, new_structured_content)


def compare_markdown_documents(
    old_markdown: str,
    new_markdown: str,
    config: ComparisonConfig | None = None,
    old_auxiliary_structured: dict[str, Any] | None = None,
    new_auxiliary_structured: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return ComparisonService(config).compare_markdown_documents(
        old_markdown,
        new_markdown,
        old_auxiliary_structured=old_auxiliary_structured,
        new_auxiliary_structured=new_auxiliary_structured,
    )


class ComparisonService:
    def __init__(self, config: ComparisonConfig | None = None) -> None:
        self.config = config or ComparisonConfig()
        self.loader = StructuredLoader()
        self.markdown_loader = MarkdownLoader()
        self.adapter = MinerUAdapter(self.config)
        self.quality_gate = QualityGate(self.config)
        self.header_footer = HeaderFooterDetector(self.config)
        self.similarity = SimilarityEngine(self.config)
        self.anchor_detector = AnchorDetector(self.config)
        self.anchor_selector = MonotonicAnchorSelector()
        self.region_builder = RegionBuilder()
        self.logical_units = LogicalUnitBuilder()
        self.dp = WindowDPAligner(self.config, self.similarity)
        self.refiner = LargeReplaceRefiner(self.config, self.similarity)
        self.coalescer = DiffCoalescer()
        self.mapper = SourceMapper()

    def compare_documents(self, old_structured_content: dict[str, Any] | str, new_structured_content: dict[str, Any] | str) -> dict[str, Any]:
        started = time.perf_counter()
        debug = DebugWriter(self.config)
        old_payload = self.loader.load(old_structured_content)
        new_payload = self.loader.load(new_structured_content)
        old_doc = self.adapter.to_canonical(old_payload, "old")
        new_doc = self.adapter.to_canonical(new_payload, "new")
        self.header_footer.mark(old_doc)
        self.header_footer.mark(new_doc)
        old_quality = self.quality_gate.evaluate(old_doc)
        new_quality = self.quality_gate.evaluate(new_doc)
        old_blocks = self.logical_units.build(old_doc.body_blocks())
        new_blocks = self.logical_units.build(new_doc.body_blocks())
        debug.write("01_old_canonical.json", old_doc)
        debug.write("02_new_canonical.json", new_doc)
        debug.write("03_old_normalized.json", [{"id": b.id, "text": b.compare_text} for b in old_blocks])
        debug.write("04_new_normalized.json", [{"id": b.id, "text": b.compare_text} for b in new_blocks])

        anchor_candidates = _deduplicate_anchors(
            self.anchor_detector.exact_unique(old_blocks, new_blocks)
            + self.anchor_detector.exact_body(old_blocks, new_blocks)
            + self.anchor_detector.exact_clause_body(old_blocks, new_blocks)
        )
        anchors = self.anchor_selector.select(anchor_candidates)
        regions = self.region_builder.build(anchors, len(old_blocks), len(new_blocks))
        debug.write("05_anchor_candidates.json", anchor_candidates)
        debug.write("06_selected_anchors.json", anchors)
        debug.write("07_regions.json", regions)

        alignments: list[Alignment] = []
        for region in regions:
            alignments.extend(self.dp.align_region(old_blocks, new_blocks, region))
        alignments = self.refiner.rescue(alignments, old_blocks, new_blocks)
        debug.write("08_dp_alignment.json", alignments)
        debug.write("09_large_replace.json", alignments)

        changes, equal_count = self._changes_from_alignments(old_doc, new_doc, old_blocks, new_blocks, alignments)
        _assign_display_groups(changes)
        debug.write("10_char_diff.json", [change.to_dict() for change in changes])
        result = {
            "comparison_id": str(uuid4()),
            "quality": {
                "old": old_quality,
                "new": new_quality,
                "warnings": old_quality["quality_warnings"] + new_quality["quality_warnings"],
            },
            "summary": {
                "insert_count": sum(1 for c in changes if c.type == "INSERT"),
                "delete_count": sum(1 for c in changes if c.type == "DELETE"),
                "equal_count": equal_count,
                "modified_regions": _modified_regions(changes),
            },
            "alignments": [asdict(alignment) for alignment in alignments],
            "changes": [change.to_dict() for change in changes],
        }
        debug.write("final_result.json", result)
        elapsed = time.perf_counter() - started
        logger.info(
            "comparison complete old_blocks=%s new_blocks=%s anchors=%s regions=%s alignments=%s changes=%s elapsed=%.3fs",
            len(old_blocks),
            len(new_blocks),
            len(anchors),
            len(regions),
            len(alignments),
            len(changes),
            elapsed,
        )
        return result

    def compare_markdown_documents(
        self,
        old_markdown: str,
        new_markdown: str,
        *,
        old_auxiliary_structured: dict[str, Any] | None = None,
        new_auxiliary_structured: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.compare_documents(
            self.markdown_loader.load(old_markdown, old_auxiliary_structured),
            self.markdown_loader.load(new_markdown, new_auxiliary_structured),
        )

    def _changes_from_alignments(
        self,
        old_doc: CanonicalDocument,
        new_doc: CanonicalDocument,
        old_blocks: list[CanonicalBlock],
        new_blocks: list[CanonicalBlock],
        alignments: list[Alignment],
    ) -> tuple[list[Change], int]:
        changes: list[Change] = []
        equal_count = 0
        for alignment in alignments:
            old_group = [old_blocks[i] for i in alignment.old_indices]
            new_group = [new_blocks[i] for i in alignment.new_indices]
            if alignment.operation == "MATCH":
                _, old_text = merge_blocks(old_group)
                _, new_text = merge_blocks(new_group)
                if old_text == new_text:
                    equal_count += 1
                    continue
                semantic_fact_changes = self._semantic_fact_changes(old_doc, new_doc, old_group, new_group, old_text, new_text, len(changes) + 1)
                if semantic_fact_changes is not None:
                    changes.extend(semantic_fact_changes)
                    continue
                key_value_changes = self._key_value_changes(old_doc, new_doc, old_group, new_group, old_text, new_text, len(changes) + 1)
                if key_value_changes is not None:
                    changes.extend(key_value_changes)
                    continue
                ops = self.coalescer.coalesce(char_diff(old_text, new_text))
                changes.extend(self._changes_from_ops(old_doc, new_doc, old_group, new_group, ops, len(changes) + 1))
            elif alignment.operation == "DELETE":
                text = "".join(block.compare_text or "" for block in old_group)
                source_old = self.mapper.range_for(old_doc, old_group, 0, len(text))
                source_new = self.mapper.range_for(new_doc, [], None, None)
                changes.append(Change(
                    f"diff_{len(changes) + 1:03d}", "DELETE", text, source_old, source_new,
                    metadata={"preview_context": {"old": _preview_context(old_group, 0, len(text))}},
                ))
            elif alignment.operation == "INSERT":
                text = "".join(block.compare_text or "" for block in new_group)
                source_old = self.mapper.range_for(old_doc, [], None, None)
                source_new = self.mapper.range_for(new_doc, new_group, 0, len(text))
                changes.append(Change(
                    f"diff_{len(changes) + 1:03d}", "INSERT", text, source_old, source_new,
                    metadata={"preview_context": {"new": _preview_context(new_group, 0, len(text))}},
                ))
        return _renumber(changes), equal_count

    def _changes_from_ops(
        self,
        old_doc: CanonicalDocument,
        new_doc: CanonicalDocument,
        old_group: list[CanonicalBlock],
        new_group: list[CanonicalBlock],
        ops: list[DiffOp],
        start_no: int,
    ) -> list[Change]:
        changes: list[Change] = []
        group_id = "modify:" + ",".join(block.id for block in old_group) + "->" + ",".join(block.id for block in new_group)
        for op in ops:
            if op.type == "EQUAL":
                continue
            if op.type == "DELETE":
                old_source = self.mapper.range_for(old_doc, old_group, op.old_start, op.old_end)
                new_source = self.mapper.range_for(new_doc, [], None, None)
                changes.append(Change(
                    f"diff_{start_no + len(changes):03d}", "DELETE", op.text, old_source, new_source,
                    metadata={
                        "group_id": group_id,
                        "preview_context": {"old": _preview_context(old_group, op.old_start, op.old_end)},
                    },
                ))
            elif op.type == "INSERT":
                old_source = self.mapper.range_for(old_doc, [], None, None)
                new_source = self.mapper.range_for(new_doc, new_group, op.new_start, op.new_end)
                changes.append(Change(
                    f"diff_{start_no + len(changes):03d}", "INSERT", op.text, old_source, new_source,
                    metadata={
                        "group_id": group_id,
                        "preview_context": {"new": _preview_context(new_group, op.new_start, op.new_end)},
                    },
                ))
        return changes

    def _semantic_fact_changes(
        self,
        old_doc: CanonicalDocument,
        new_doc: CanonicalDocument,
        old_group: list[CanonicalBlock],
        new_group: list[CanonicalBlock],
        old_text: str,
        new_text: str,
        start_no: int,
    ) -> list[Change] | None:
        old_facts = _parse_compare_facts(old_text)
        new_facts = _parse_compare_facts(new_text)
        if not old_facts or not new_facts:
            return None
        shared_keys = set(old_facts) & set(new_facts)
        if not shared_keys:
            return None
        changes: list[Change] = []
        for key in sorted(shared_keys):
            if old_facts[key].value == new_facts[key].value:
                continue
            old_source = self.mapper.range_for(old_doc, old_group, None, None)
            new_source = self.mapper.range_for(new_doc, new_group, None, None)
            if old_facts[key].value:
                changes.append(Change(f"diff_{start_no + len(changes):03d}", "DELETE", old_facts[key].value, old_source, self.mapper.range_for(new_doc, [], None, None), metadata={"alignment": "SEMANTIC_FACT", "key": key, "preview_context": {"old": _preview_context(old_group, None, None)}}))
            if new_facts[key].value:
                changes.append(Change(f"diff_{start_no + len(changes):03d}", "INSERT", new_facts[key].value, self.mapper.range_for(old_doc, [], None, None), new_source, metadata={"alignment": "SEMANTIC_FACT", "key": key, "preview_context": {"new": _preview_context(new_group, None, None)}}))
        for key in sorted(set(old_facts) - set(new_facts)):
            changes.append(Change(f"diff_{start_no + len(changes):03d}", "DELETE", old_facts[key].value, self.mapper.range_for(old_doc, old_group, None, None), self.mapper.range_for(new_doc, [], None, None), metadata={"alignment": "SEMANTIC_FACT", "key": key, "preview_context": {"old": _preview_context(old_group, None, None)}}))
        for key in sorted(set(new_facts) - set(old_facts)):
            changes.append(Change(f"diff_{start_no + len(changes):03d}", "INSERT", new_facts[key].value, self.mapper.range_for(old_doc, [], None, None), self.mapper.range_for(new_doc, new_group, None, None), metadata={"alignment": "SEMANTIC_FACT", "key": key, "preview_context": {"new": _preview_context(new_group, None, None)}}))
        return changes

    def _key_value_changes(
        self,
        old_doc: CanonicalDocument,
        new_doc: CanonicalDocument,
        old_group: list[CanonicalBlock],
        new_group: list[CanonicalBlock],
        old_text: str,
        new_text: str,
        start_no: int,
    ) -> list[Change] | None:
        if not self.config.key_value_match_enabled or len(old_group) != 1 or len(new_group) != 1:
            return None
        old_kv = parse_key_value(old_text)
        new_kv = parse_key_value(new_text)
        if not old_kv or not new_kv or old_kv.key != new_kv.key:
            return None
        changes: list[Change] = []
        if old_kv.value:
            old_source = self.mapper.range_for(old_doc, old_group, old_kv.value_start, old_kv.value_start + len(old_kv.value))
            new_source = self.mapper.range_for(new_doc, [], None, None)
            changes.append(Change(f"diff_{start_no:03d}", "DELETE", old_kv.value, old_source, new_source, metadata={"alignment": "KEY_VALUE", "key": old_kv.key, "preview_context": {"old": _preview_context(old_group, old_kv.value_start, old_kv.value_start + len(old_kv.value))}}))
        if new_kv.value:
            old_source = self.mapper.range_for(old_doc, [], None, None)
            new_source = self.mapper.range_for(new_doc, new_group, new_kv.value_start, new_kv.value_start + len(new_kv.value))
            changes.append(Change(f"diff_{start_no + len(changes):03d}", "INSERT", new_kv.value, old_source, new_source, metadata={"alignment": "KEY_VALUE", "key": new_kv.key, "preview_context": {"new": _preview_context(new_group, new_kv.value_start, new_kv.value_start + len(new_kv.value))}}))
        return changes


def _renumber(changes: list[Change]) -> list[Change]:
    for index, change in enumerate(changes, start=1):
        change.id = f"diff_{index:03d}"
    return changes


def _deduplicate_anchors(anchors):
    by_pair = {}
    for anchor in anchors:
        key = (anchor.old_index, anchor.new_index)
        current = by_pair.get(key)
        if current is None or anchor.weight * anchor.score > current.weight * current.score:
            by_pair[key] = anchor
    return list(by_pair.values())


def _modified_regions(changes: list[Change]) -> int:
    count = 0
    i = 0
    while i < len(changes):
        if i + 1 < len(changes) and changes[i].type == "DELETE" and changes[i + 1].type == "INSERT":
            count += 1
            i += 2
        else:
            i += 1
    return count


def _assign_display_groups(changes: list[Change]) -> None:
    """Give paired old/new operations a stable id for spatial cross-location."""
    index = 0
    group_number = 1
    while index < len(changes):
        current = changes[index]
        existing = current.metadata.get("group_id")
        if existing:
            index += 1
            continue
        nxt = changes[index + 1] if index + 1 < len(changes) else None
        if nxt is not None and nxt.type != current.type and not nxt.metadata.get("group_id"):
            group_id = f"pair_{group_number:04d}"
            current.metadata["group_id"] = group_id
            nxt.metadata["group_id"] = group_id
            group_number += 1
            index += 2
            continue
        current.metadata["group_id"] = f"single_{group_number:04d}"
        group_number += 1
        index += 1


def _parse_compare_facts(text: str) -> dict[str, SemanticFact]:
    facts: dict[str, SemanticFact] = {}
    if "|" not in text:
        return facts
    for part in text.split("|"):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        key = key.strip()
        if key:
            facts[key] = SemanticFact(key, value.strip())
    return facts


def _preview_context(blocks: list[CanonicalBlock], start: int | None, end: int | None, radius: int = 48) -> str:
    """Build a stable locator query around a change without changing diff text."""
    text = "".join(block.compare_text or "" for block in blocks)
    if not text:
        return ""
    if start is None or end is None:
        return text[: radius * 2]
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return text[left:right]
