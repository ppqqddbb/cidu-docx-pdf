from __future__ import annotations

from backend.comparison.models.diff import DiffOp


class DiffCoalescer:
    def coalesce(self, ops: list[DiffOp]) -> list[DiffOp]:
        merged: list[DiffOp] = []
        for op in ops:
            if not op.text:
                continue
            if merged and merged[-1].type == op.type and _touches(merged[-1], op):
                prev = merged[-1]
                prev.text += op.text
                prev.old_start = _min_none(prev.old_start, op.old_start)
                prev.old_end = _max_none(prev.old_end, op.old_end)
                prev.new_start = _min_none(prev.new_start, op.new_start)
                prev.new_end = _max_none(prev.new_end, op.new_end)
            else:
                merged.append(op)
        return _expand_unit_number_replacements(merged)


def _touches(left: DiffOp, right: DiffOp) -> bool:
    return (
        (left.old_end is None or right.old_start is None or left.old_end == right.old_start)
        and (left.new_end is None or right.new_start is None or left.new_end == right.new_start)
    )


def _min_none(left: int | None, right: int | None) -> int | None:
    values = [v for v in (left, right) if v is not None]
    return min(values) if values else None


def _max_none(left: int | None, right: int | None) -> int | None:
    values = [v for v in (left, right) if v is not None]
    return max(values) if values else None


def _expand_unit_number_replacements(ops: list[DiffOp]) -> list[DiffOp]:
    expanded: list[DiffOp] = []
    i = 0
    while i < len(ops):
        prev = expanded[-1] if expanded else None
        current = ops[i]
        nxt = ops[i + 1] if i + 1 < len(ops) else None
        after = ops[i + 2] if i + 2 < len(ops) else None
        if (
            prev
            and current.type == "DELETE"
            and nxt
            and nxt.type == "INSERT"
            and after
            and after.type == "EQUAL"
            and after.text[:1].isalpha()
            and current.text
            and nxt.text
            and current.text[0].isdigit()
            and nxt.text[0].isdigit()
        ):
            suffix = _trailing_digits(prev.text)
            if suffix:
                prev.text = prev.text[: -len(suffix)]
                if prev.old_end is not None:
                    prev.old_end -= len(suffix)
                if prev.new_end is not None:
                    prev.new_end -= len(suffix)
                if not prev.text:
                    expanded.pop()
                current.text = suffix + current.text
                nxt.text = suffix + nxt.text
                if current.old_start is not None:
                    current.old_start -= len(suffix)
                if nxt.new_start is not None:
                    nxt.new_start -= len(suffix)
        expanded.append(current)
        i += 1
    return expanded


def _trailing_digits(text: str) -> str:
    index = len(text)
    while index > 0 and text[index - 1].isdigit():
        index -= 1
    return text[index:]
