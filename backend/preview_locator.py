from __future__ import annotations

import re
import unicodedata
from html import unescape
from pathlib import Path
from typing import Any

import fitz


_MARKUP_RE = re.compile(r"<[^>]+>|\*\*|__|`|#+|\[|\]")


def attach_preview_locations(result: dict[str, Any], old_pdf: Path, new_pdf: Path) -> None:
    old_document = fitz.open(str(old_pdf))
    new_document = fitz.open(str(new_pdf))
    caches: dict[str, dict[str, list[dict[str, Any]]]] = {"old": {}, "new": {}}
    indices = {"old": _build_text_index(old_document), "new": _build_text_index(new_document)}
    cursors: dict[str, dict[str, float]] = {
        "old": {"page_index": 0.0, "y": 0.0},
        "new": {"page_index": 0.0, "y": 0.0},
    }
    group_positions: dict[str, dict[str, float]] = {}
    try:
        for change in result.get("changes", []):
            if not isinstance(change, dict):
                continue
            if change.get("type") == "DELETE":
                _attach_side(change, "old", old_document, caches["old"], indices["old"], cursors["old"], group_positions)
            elif change.get("type") == "INSERT":
                _attach_side(change, "new", new_document, caches["new"], indices["new"], cursors["new"], group_positions)
    finally:
        old_document.close()
        new_document.close()


def _attach_side(
    change: dict[str, Any],
    side: str,
    document: fitz.Document,
    cache: dict[str, list[dict[str, Any]]],
    text_index: list[dict[str, Any]],
    cursor: dict[str, float],
    group_positions: dict[str, dict[str, float]],
) -> None:
    source = change.get(side)
    if not isinstance(source, dict):
        return
    group_id = str((change.get("metadata") or {}).get("group_id") or "")
    text = _clean_text(str(change.get("text") or ""))
    if not text:
        return
    context = _clean_text(str((change.get("metadata") or {}).get("preview_context", {}).get(side) or ""))
    context_locations = _locate_best_context(document, context, cache, text_index)
    locations = _locate(document, text, cache, text_index)
    context_locked = False
    if context_locations and locations:
        locations = _nearest_on_context_page(locations, context_locations[0])
        context_locked = bool(locations)
    if not locations and len(text) > 8:
        locations = _locate_best_context(document, text, cache, text_index)
    if not locations:
        # A block-level MinerU bbox describes the whole paragraph, not the
        # changed substring.  Omitting an uncertain mark is safer than
        # highlighting unrelated text.
        source.pop("preview_bbox", None)
        source.pop("preview_bboxes", None)
        return
    page_hint = source.get("page_index")
    if not context_locked and page_hint is not None:
        hinted = [item for item in locations if item["page_index"] == int(page_hint)]
        if hinted:
            locations = hinted
    counterpart = group_positions.get(group_id)
    first = locations[0] if context_locked else _select_monotonic_location(
        locations,
        cursor,
        counterpart=counterpart,
        page_count=document.page_count,
    )
    source["page_index"] = first["page_index"]
    source["bbox"] = first["bbox"]
    source["preview_bbox"] = first["bbox"]
    source["preview_bboxes"] = first.get("bboxes") or [first["bbox"]]
    change.setdefault("metadata", {})["preview_locations"] = [first]
    cursor["page_index"] = float(first["page_index"])
    cursor["y"] = float(first["bbox"][1])
    if group_id:
        group_positions[group_id] = {
            "page_ratio": first["page_index"] / max(1, document.page_count - 1),
            "y_ratio": float(first["bbox"][1]) / 1000.0,
        }


def locate_text_in_pdf(pdf_path: Path, text: str) -> list[dict[str, Any]]:
    if not pdf_path.exists():
        return []
    document = fitz.open(str(pdf_path))
    try:
        return _locate(document, text, {}, _build_text_index(document))
    finally:
        document.close()


def _search(document: fitz.Document, text: str) -> list[dict[str, Any]]:
    if not text:
        return []
    locations: list[dict[str, Any]] = []
    for page_index in range(document.page_count):
        page = document.load_page(page_index)
        width = float(page.rect.width) or 1.0
        height = float(page.rect.height) or 1.0
        for rect in page.search_for(text, quads=False):
            bbox = [
                max(0.0, min(1000.0, rect.x0 / width * 1000.0)),
                max(0.0, min(1000.0, rect.y0 / height * 1000.0)),
                max(0.0, min(1000.0, rect.x1 / width * 1000.0)),
                max(0.0, min(1000.0, rect.y1 / height * 1000.0)),
            ]
            locations.append(
                {
                    "page_index": page_index,
                    "bbox": bbox,
                    "bboxes": [bbox],
                }
            )
    return locations


def _clean_text(text: str) -> str:
    cleaned = unescape(_MARKUP_RE.sub("", text))
    cleaned = re.sub(r"^\s*[-*+]\s*", "", cleaned)
    cleaned = cleaned.replace("|", " ")
    cleaned = re.sub(r"[：:]{2,}", "：", cleaned)
    return cleaned.strip()


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _locate_best_context(
    document: fitz.Document,
    context: str,
    cache: dict[str, list[dict[str, Any]]],
    text_index: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    compact = _compact_text(context)
    if not compact:
        return []
    candidates = [compact]
    for size in (48, 32, 20, 12):
        if len(compact) > size:
            candidates.extend(compact[start : start + size] for start in (0, max(0, (len(compact) - size) // 2), len(compact) - size))
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        locations = _locate(document, candidate, cache, text_index)
        if locations:
            return locations
    return []


def _locate(
    document: fitz.Document,
    text: str,
    cache: dict[str, list[dict[str, Any]]],
    text_index: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    key = text.strip()
    if not key:
        return []
    if key not in cache:
        cache[key] = _search_index(text_index, key) or _search(document, key) or _search(document, _compact_text(key))
    return cache[key]


def _build_text_index(document: fitz.Document) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    for page_index in range(document.page_count):
        page = document.load_page(page_index)
        width = float(page.rect.width) or 1.0
        height = float(page.rect.height) or 1.0
        chunks: list[str] = []
        spans: list[tuple[int, int, list[float]]] = []
        cursor = 0
        for word in page.get_text("words", sort=True):
            token = _compact_text(str(word[4]))
            if not token:
                continue
            start = cursor
            chunks.append(token)
            cursor += len(token)
            spans.append((start, cursor, [word[0] / width * 1000, word[1] / height * 1000, word[2] / width * 1000, word[3] / height * 1000]))
        pages.append({"text": "".join(chunks), "spans": spans})
    return pages


def _search_index(text_index: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    needle = _compact_text(unicodedata.normalize("NFKC", query))
    if not needle:
        return []
    results: list[dict[str, Any]] = []
    for page_index, page in enumerate(text_index):
        haystack = unicodedata.normalize("NFKC", page["text"])
        start = haystack.find(needle)
        while start >= 0:
            end = start + len(needle)
            boxes = [bbox for span_start, span_end, bbox in page["spans"] if span_end > start and span_start < end]
            if boxes:
                line_boxes = _line_boxes(boxes)
                results.append(
                    {
                        "page_index": page_index,
                        "bbox": _union_boxes(line_boxes),
                        "bboxes": line_boxes,
                    }
                )
            start = haystack.find(needle, start + max(1, len(needle)))
    return results


def _union_boxes(boxes: list[list[float]]) -> list[float]:
    return [min(box[0] for box in boxes), min(box[1] for box in boxes), max(box[2] for box in boxes), max(box[3] for box in boxes)]


def _line_boxes(boxes: list[list[float]]) -> list[list[float]]:
    """Keep multi-line matches as separate rectangles instead of one large box."""
    lines: list[list[list[float]]] = []
    for box in sorted(boxes, key=lambda item: (item[1], item[0])):
        if not lines or abs(lines[-1][0][1] - box[1]) > 3.0:
            lines.append([box])
        else:
            lines[-1].append(box)
    return [_union_boxes(line) for line in lines]


def _nearest_on_context_page(locations: list[dict[str, Any]], context: dict[str, Any]) -> list[dict[str, Any]]:
    same_page = [item for item in locations if item["page_index"] == context["page_index"]]
    if not same_page:
        return []
    cx = (context["bbox"][0] + context["bbox"][2]) / 2
    cy = (context["bbox"][1] + context["bbox"][3]) / 2
    return sorted(
        same_page,
        key=lambda item: abs((item["bbox"][0] + item["bbox"][2]) / 2 - cx) + abs((item["bbox"][1] + item["bbox"][3]) / 2 - cy),
    )


def _select_monotonic_location(
    locations: list[dict[str, Any]],
    cursor: dict[str, float],
    *,
    counterpart: dict[str, float] | None = None,
    page_count: int = 1,
) -> dict[str, Any]:
    """Choose the next occurrence in reading order instead of the first duplicate."""
    current_page = int(cursor["page_index"])
    current_y = cursor["y"]
    forward = [
        item for item in locations
        if item["page_index"] > current_page
        or (item["page_index"] == current_page and float(item["bbox"][1]) + 2.0 >= current_y)
    ]
    candidates = forward or locations
    if counterpart is not None:
        return min(
            candidates,
            key=lambda item: (
                abs(item["page_index"] / max(1, page_count - 1) - counterpart["page_ratio"]) * 4.0
                + abs(float(item["bbox"][1]) / 1000.0 - counterpart["y_ratio"]),
                item["page_index"],
                float(item["bbox"][1]),
            ),
        )
    return min(
        candidates,
        key=lambda item: (
            max(0, item["page_index"] - current_page),
            abs(float(item["bbox"][1]) - current_y) if item["page_index"] == current_page else float(item["bbox"][1]),
        ),
    )
