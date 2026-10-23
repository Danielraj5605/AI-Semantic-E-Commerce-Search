"""Retrieval metrics. Pure functions over ranked lists of product names."""

from typing import Iterable, Sequence


def precision_at_k(ranked: Sequence[str], relevant: Iterable[str], k: int = 5) -> float:
    """Share of the top-k slots that hold a relevant item.

    The denominator is always k, so a query with a single relevant product can
    score at most 1/k. That is the textbook definition; recall and MRR below are
    reported alongside it for exactly that reason.
    """
    rel = set(relevant)
    return sum(1 for name in ranked[:k] if name in rel) / k


def recall_at_k(ranked: Sequence[str], relevant: Iterable[str], k: int = 5) -> float:
    """Share of all relevant items that appear in the top k."""
    rel = set(relevant)
    if not rel:
        return 0.0
    return sum(1 for name in ranked[:k] if name in rel) / len(rel)


def reciprocal_rank(ranked: Sequence[str], relevant: Iterable[str]) -> float:
    """1 / rank of the first relevant item, or 0 if none was returned."""
    rel = set(relevant)
    for position, name in enumerate(ranked, start=1):
        if name in rel:
            return 1.0 / position
    return 0.0


def hit_at_1(ranked: Sequence[str], relevant: Iterable[str]) -> float:
    """1 if the very first result is relevant."""
    return 1.0 if ranked and ranked[0] in set(relevant) else 0.0


def reciprocal_rank_fusion(rankings: Sequence[Sequence[str]], k: int = 60) -> list[str]:
    """Merge several rankings into one (Cormack et al. 2009). Higher is better."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for position, name in enumerate(ranking, start=1):
            scores[name] = scores.get(name, 0.0) + 1.0 / (k + position)
    return [name for name, _ in sorted(scores.items(), key=lambda item: -item[1])]


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0
