from __future__ import annotations


def accuracy(results: list[bool]) -> float:
    if not results:
        return 0.0
    return round(sum(results) / len(results), 4)
