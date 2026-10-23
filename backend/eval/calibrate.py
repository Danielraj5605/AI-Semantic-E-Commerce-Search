"""Turn similarity scores into measured confidence (the Trust layer's evidence).

    python -m eval.calibrate

Runs every labelled query, pools the (score, relevant?) pair for each result the
user would actually see, bins by score, and smooths the bin precisions so they never
decrease with score (pool-adjacent-violators). Writes eval/calibration.json, which
the API serves and the UI shows beside each result.

Read the number as a *lower bound*: a result counts as relevant only if it is in the
query's `relevant` labels, so a good product nobody labelled is counted as a miss.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.db.session import async_session  # noqa: E402
from app.semantics.trust import CALIBRATION_PATH, pool_adjacent_violators  # noqa: E402
from app.services.search_service import semantic_search  # noqa: E402
from eval.run_eval import load_queries  # noqa: E402

EDGES = [0.25, 0.32, 0.40, 0.50, 0.60, 1.01]
POOL = 20


async def collect() -> list[tuple[float, bool]]:
    pairs = []
    async with async_session() as db:
        for q in load_queries()["queries"]:
            results, _ = await semantic_search(db, q["query"], limit=POOL)
            relevant = set(q["relevant"])
            pairs += [(r["score"], r["product"]["name"] in relevant) for r in results]
    return pairs


def build(pairs: list[tuple[float, bool]]) -> dict:
    counts = []
    for lo, hi in zip(EDGES, EDGES[1:]):
        inside = [rel for s, rel in pairs if lo <= s < hi]
        counts.append((sum(inside), len(inside)))
    smooth = pool_adjacent_violators(counts)
    bins = [
        {"lo": lo, "hi": min(hi, 1.0), "relevant": r, "n": n,
         "precision": round(p, 3), "raw_precision": round(r / n, 3) if n else None}
        for (lo, hi), (r, n), p in zip(zip(EDGES, EDGES[1:]), counts, smooth)
    ]
    return {
        "model": get_settings().embedding_model,
        "min_similarity": get_settings().min_similarity,
        "queries": len(load_queries()["queries"]),
        "results": len(pairs),
        "method": "precision of returned results by similarity bin, monotone-smoothed (PAV)",
        "caveat": "lower bound: unlabelled results count as not relevant; labels are a first pass",
        "bins": bins,
    }


if __name__ == "__main__":
    cal = build(asyncio.run(collect()))
    CALIBRATION_PATH.write_text(json.dumps(cal, indent=2) + "\n", encoding="utf-8")
    for b in cal["bins"]:
        print(f"{b['lo']:.2f}-{b['hi']:.2f}  n={b['n']:3d}  raw={b['raw_precision']}  calibrated={b['precision']}")
