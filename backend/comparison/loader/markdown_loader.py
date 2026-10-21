from __future__ import annotations

import re
from html import escape
from pathlib import Path
from typing import Any


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_LIST_RE = re.compile(r"^\s*(?:[-*+]\s+|(?:\(?\d{1,3}\)?|（\d{1,3}）)[.、)]?\s+)(.+)$")
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*$")


class MarkdownLoader:
    """Convert MinerU Markdown into the neutral block input used by comparison."""

    def load(self, value: str | Path, auxiliary_structured: dict[str, Any] | None = None) -> dict[str, Any]:
        text = self._read(value)
        blocks: list[dict[str, Any]] = []
        paragraph: list[str] = []
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        index = 0

        def flush_paragraph() -> None:
            if paragraph:
                blocks.append({"type": "text", "content": "".join(part.strip() for part in paragraph)})
                paragraph.clear()

        while index < len(lines):
            line = lines[index]
            heading = _HEADING_RE.match(line.strip())
            if heading:
                flush_paragraph()
                level = len(heading.group(1))
                title = heading.group(2).strip()
                blocks.append({"type": "paragraph_title", "level": level, "content": title})
                index += 1
                continue
            if not line.strip():
                flush_paragraph()
                index += 1
                continue
            if _is_table_line(line):
                flush_paragraph()
                table_lines: list[str] = []
                while index < len(lines) and _is_table_line(lines[index]):
                    table_lines.append(lines[index])
                    index += 1
                blocks.append({"type": "table", "content": _markdown_table_to_html(table_lines)})
                continue
            if _LIST_RE.match(line):
                flush_paragraph()
                blocks.append({"type": "list", "content": line.strip()})
                index += 1
                continue
            paragraph.append(line)
            index += 1
        flush_paragraph()
        pages = [{"page_idx": None, "blocks": blocks}]
        pages.extend(_auxiliary_pages(auxiliary_structured))
        return {
            "pages": pages,
            "metadata": {"source_format": "mineru_markdown"},
        }

    @staticmethod
    def _read(value: str | Path) -> str:
        if isinstance(value, Path):
            return value.read_text(encoding="utf-8-sig")
        if "\n" not in value and len(value) < 240:
            candidate = Path(value)
            if candidate.exists():
                return candidate.read_text(encoding="utf-8-sig")
        return value


def _is_table_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def _markdown_table_to_html(lines: list[str]) -> str:
    rows: list[list[str]] = []
    for line in lines:
        if _TABLE_SEPARATOR_RE.match(line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        rows.append(cells)
    rendered: list[str] = ["<table>"]
    for row_index, row in enumerate(rows):
        tag = "th" if row_index == 0 else "td"
        rendered.append("<tr>" + "".join(f"<{tag}>{escape(cell)}</{tag}>" for cell in row) + "</tr>")
    rendered.append("</table>")
    return "".join(rendered)


def _auxiliary_pages(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return []
    accepted = {"header", "footer", "page_header", "page_footer", "page_number"}
    pages: list[dict[str, Any]] = []
    for page_position, page in enumerate(payload.get("pages") or []):
        if not isinstance(page, dict):
            continue
        blocks = [
            dict(block)
            for block in page.get("blocks") or []
            if isinstance(block, dict) and str(block.get("type") or "").lower() in accepted
        ]
        if blocks:
            pages.append({"page_idx": page.get("page_idx", page_position), "blocks": blocks})
    return pages
