"""Evaluate keyword vs semantic (vs a hybrid experiment) on the labelled queries.

    python -m eval.run_eval

Runs against whichever database settings point at, calling the same service
functions the API uses, and writes eval/results.json and eval/RESULTS.md.
Semantic uses the production relevance floor; the point is to measure what a
user would actually get.
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
from app.services.search_service import keyword_search, semantic_search  # noqa: E402
from eval.metrics import (  # noqa: E402
    hit_at_1, mean, precision_at_k, recall_at_k, reciprocal_rank, reciprocal_rank_fusion,
)

HERE = Path(__file__).resolve().parent
K = 5
POOL = 20  # how deep each method is retrieved before fusion
METHODS = ("keyword", "semantic", "hybrid")


def load_queries() -> dict:
    return json.loads((HERE / "queries.json").read_text(encoding="utf-8"))


async def rank_all(db, query: str) -> dict[str, list[str]]:
    sem, _ = await semantic_search(db, query, limit=POOL)
    kw, _ = await keyword_search(db, query, limit=POOL)
    sem_names = [r["product"]["name"] for r in sem]
    kw_names = [r["product"]["name"] for r in kw]
    return {
        "keyword": kw_names,
        "semantic": sem_names,
        # Experiment only (not in the API): fuse the two lists by reciprocal rank.
        "hybrid": reciprocal_rank_fusion([sem_names, kw_names]),
    }


def score(ranked: list[str], relevant: list[str]) -> dict[str, float]:
    return {
        "p@5": precision_at_k(ranked, relevant, K),
        "recall@5": recall_at_k(ranked, relevant, K),
        "mrr": reciprocal_rank(ranked, relevant),
        "hit@1": hit_at_1(ranked, relevant),
    }


async def evaluate() -> dict:
    spec = load_queries()
    rows = []
    async with async_session() as db:
        for q in spec["queries"]:
            ranked = await rank_all(db, q["query"])
            entry = {**q, "ranked": {m: names[:K] for m, names in ranked.items()}, "returned": {m: len(n) for m, n in ranked.items()}}
            if q["relevant"]:
                entry["scores"] = {m: score(ranked[m], q["relevant"]) for m in METHODS}
            rows.append(entry)

    summary: dict[str, dict] = {}
    for cls in [*(c for c in spec["classes"] if c != "no_answer"), "overall"]:
        subset = [r for r in rows if r["relevant"] and (cls == "overall" or r["class"] == cls)]
        summary[cls] = {
            "queries": len(subset),
            **{
                m: {metric: round(mean([r["scores"][m][metric] for r in subset]), 3) for metric in ("p@5", "recall@5", "mrr", "hit@1")}
                for m in METHODS
            },
        }

    negatives = [r for r in rows if not r["relevant"]]
    abstention = {
        m: {"queries": len(negatives), "correctly_empty": sum(1 for r in negatives if r["returned"][m] == 0),
            "results_returned": [r["returned"][m] for r in negatives]}
        for m in METHODS
    }
    return {
        "settings": {"embedding_model": get_settings().embedding_model, "min_similarity": get_settings().min_similarity, "k": K},
        "summary": summary, "abstention": abstention, "queries": rows, "classes": spec["classes"],
    }


def _cell(v: float) -> str:
    return f"{v:.2f}"


def render_markdown(result: dict) -> str:
    out = ["# Evaluation results", ""]
    s = result["settings"]
    out += [
        f"Model `{s['embedding_model']}`, relevance floor {s['min_similarity']}, k = {s['k']}. "
        "Labels were drafted from the catalogue text (see `queries.json`); treat them as a first pass to be reviewed.", "",
        "**P@5** is the textbook definition (relevant items in the top 5, divided by 5), so a query with only one "
        "relevant product can score at most 0.20. **Recall@5**, **MRR** and **Hit@1** are shown beside it for that reason.", "",
        "## Summary", "",
        "| Query class | n | Method | P@5 | Recall@5 | MRR | Hit@1 |", "|---|---|---|---|---|---|---|",
    ]
    for cls, block in result["summary"].items():
        for i, m in enumerate(METHODS):
            v = block[m]
            out.append(f"| {cls if i == 0 else ''} | {block['queries'] if i == 0 else ''} | {m} | "
                       f"{_cell(v['p@5'])} | {_cell(v['recall@5'])} | {_cell(v['mrr'])} | {_cell(v['hit@1'])} |")

    a = result["abstention"]
    out += ["", "## Queries with no right answer", "",
            "Nothing in the catalogue matches these. The correct behaviour is an empty result.", "",
            "| Method | Correctly empty | Results returned per query |", "|---|---|---|"]
    for m in METHODS:
        out.append(f"| {m} | {a[m]['correctly_empty']} / {a[m]['queries']} | {a[m]['results_returned']} |")

    out += ["", "## Per query", "", "| ID | Query | Relevant | Keyword MRR | Semantic MRR | Hybrid MRR |", "|---|---|---|---|---|---|"]
    for r in result["queries"]:
        if r["relevant"]:
            sc = r["scores"]
            out.append(f"| {r['id']} | {r['query']} | {len(r['relevant'])} | {_cell(sc['keyword']['mrr'])} | "
                       f"{_cell(sc['semantic']['mrr'])} | {_cell(sc['hybrid']['mrr'])} |")

    out += ["", "## Where semantic search missed", ""]
    misses = [r for r in result["queries"] if r["relevant"] and r["scores"]["semantic"]["hit@1"] < 1]
    if not misses:
        out.append("None: the first semantic result was relevant for every query.")
    for r in misses:
        out += [f"**{r['id']} - \"{r['query']}\"** (wanted: {', '.join(r['relevant'])})", ""]
        out += [f"{i}. {n}{'  <- relevant' if n in r['relevant'] else ''}" for i, n in enumerate(r["ranked"]["semantic"], 1)] or ["_no results_"]
        out.append("")
    return "\n".join(out) + "\n"


def main() -> None:
    result = asyncio.run(evaluate())
    (HERE / "results.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    (HERE / "RESULTS.md").write_text(render_markdown(result), encoding="utf-8")
    print(render_markdown(result))


if __name__ == "__main__":
    main()
