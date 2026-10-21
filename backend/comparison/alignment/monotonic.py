from __future__ import annotations

from backend.comparison.models.alignment import Anchor


class MonotonicAnchorSelector:
    def select(self, anchors: list[Anchor]) -> list[Anchor]:
        ordered = sorted(anchors, key=lambda a: (a.old_index, a.new_index))
        if not ordered:
            return []
        n = len(ordered)
        score = [a.weight * a.score for a in ordered]
        prev = [-1] * n
        for i in range(n):
            for j in range(i):
                if ordered[j].old_index < ordered[i].old_index and ordered[j].new_index < ordered[i].new_index:
                    candidate = score[j] + ordered[i].weight * ordered[i].score
                    if candidate > score[i]:
                        score[i] = candidate
                        prev[i] = j
        best = max(range(n), key=lambda i: score[i])
        chain: list[Anchor] = []
        while best != -1:
            chain.append(ordered[best])
            best = prev[best]
        return list(reversed(chain))
