from __future__ import annotations


def ngrams(text: str, n: int) -> set[str]:
    if not text:
        return set()
    if len(text) <= n:
        return {text}
    return {text[i : i + n] for i in range(len(text) - n + 1)}


def dice_similarity(left: str, right: str, n: int = 3) -> float:
    a = ngrams(left, n)
    b = ngrams(right, n)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return 2 * len(a & b) / (len(a) + len(b))
