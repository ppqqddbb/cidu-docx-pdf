from __future__ import annotations

from backend.comparison.models.diff import DiffOp


def char_diff(old: str, new: str) -> list[DiffOp]:
    old_len, new_len = len(old), len(new)
    dp = [[0] * (new_len + 1) for _ in range(old_len + 1)]
    for i in range(old_len - 1, -1, -1):
        for j in range(new_len - 1, -1, -1):
            if old[i] == new[j]:
                dp[i][j] = dp[i + 1][j + 1] + 1
            else:
                dp[i][j] = max(dp[i + 1][j], dp[i][j + 1])
    ops: list[DiffOp] = []
    i = j = 0
    while i < old_len and j < new_len:
        if old[i] == new[j]:
            ops.append(DiffOp("EQUAL", old[i], i, i + 1, j, j + 1))
            i += 1
            j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            ops.append(DiffOp("DELETE", old[i], i, i + 1, None, None))
            i += 1
        else:
            ops.append(DiffOp("INSERT", new[j], None, None, j, j + 1))
            j += 1
    while i < old_len:
        ops.append(DiffOp("DELETE", old[i], i, i + 1, None, None))
        i += 1
    while j < new_len:
        ops.append(DiffOp("INSERT", new[j], None, None, j, j + 1))
        j += 1
    return ops
