"""The evaluation harness: metric maths, label integrity, and a regression guard."""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from eval.metrics import (
    hit_at_1, mean, precision_at_k, recall_at_k, reciprocal_rank, reciprocal_rank_fusion,
)

BACKEND = Path(__file__).resolve().parent.parent
QUERIES = json.loads((BACKEND / "eval" / "queries.json").read_text(encoding="utf-8"))


# ---------- metric maths ----------

def test_precision_denominator_is_always_k():
    assert precision_at_k(["a", "b", "c"], ["a"], k=5) == pytest.approx(0.2)
    assert precision_at_k(["a", "b", "c", "d", "e"], ["a", "b"], k=5) == pytest.approx(0.4)


def test_precision_ignores_items_beyond_k():
    assert precision_at_k(["x", "x", "x", "x", "x", "a"], ["a"], k=5) == 0.0


def test_recall():
    assert recall_at_k(["a", "x", "b"], ["a", "b", "c", "d"], k=5) == pytest.approx(0.5)
    assert recall_at_k(["a"], [], k=5) == 0.0


def test_reciprocal_rank_and_hit():
    assert reciprocal_rank(["x", "a"], ["a"]) == 0.5
    assert reciprocal_rank(["x"], ["a"]) == 0.0
    assert hit_at_1(["a", "x"], ["a"]) == 1.0
    assert hit_at_1(["x", "a"], ["a"]) == 0.0
    assert hit_at_1([], ["a"]) == 0.0


def test_fusion_rewards_agreement():
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["c", "a", "d"]])
    assert fused[0] == "a" and set(fused) == {"a", "b", "c", "d"}


def test_mean_of_nothing_is_zero():
    assert mean([]) == 0.0


# ---------- label integrity ----------

def test_query_ids_are_unique_and_classes_declared():
    ids = [q["id"] for q in QUERIES["queries"]]
    assert len(ids) == len(set(ids))
    assert {q["class"] for q in QUERIES["queries"]} <= set(QUERIES["classes"])


def test_every_class_has_at_least_ten_or_three_queries():
    by = {}
    for q in QUERIES["queries"]:
        by[q["class"]] = by.get(q["class"], 0) + 1
    assert all(by[c] >= 10 for c in ("exact", "paraphrase", "vague"))
    assert by["no_answer"] >= 3


def test_every_label_names_a_real_product(db_path):
    """A typo in a label would silently count as a miss, so check them all."""
    con = sqlite3.connect(db_path)
    try:
        names = {r[0] for r in con.execute("SELECT name FROM products")}
    finally:
        con.close()
    for q in QUERIES["queries"]:
        for label in q["relevant"]:
            assert label in names, f'{q["id"]}: unknown product {label!r}'


def test_no_answer_queries_have_no_labels():
    assert all(q["relevant"] == [] for q in QUERIES["queries"] if q["class"] == "no_answer")
    assert all(q["relevant"] for q in QUERIES["queries"] if q["class"] != "no_answer")


# ---------- regression guard ----------

@pytest.fixture(scope="module")
def evaluation(db_path):
    """Run the whole evaluation in a subprocess against the temp DB (no files written)."""
    code = (
        "import asyncio, json; from eval.run_eval import evaluate; "
        "r = asyncio.run(evaluate()); print('RESULT' + json.dumps({k: r[k] for k in ('summary', 'abstention')}))"
    )
    env = {**os.environ, "USE_LOCAL_DB": "true", "LOCAL_DB_PATH": db_path.as_posix(), "HF_HUB_OFFLINE": "1"}
    out = subprocess.run([sys.executable, "-W", "ignore", "-c", code], cwd=BACKEND,
                         capture_output=True, text=True, env=env, timeout=240)
    line = next((l for l in out.stdout.splitlines() if l.startswith("RESULT")), None)
    assert line, out.stderr[-800:]
    return json.loads(line[len("RESULT"):])


def test_semantic_beats_keyword_where_meaning_matters(evaluation):
    s = evaluation["summary"]
    for cls in ("paraphrase", "vague"):
        assert s[cls]["semantic"]["mrr"] > s[cls]["keyword"]["mrr"] + 0.3, cls


def test_semantic_is_not_worse_on_exact_lookups(evaluation):
    s = evaluation["summary"]["exact"]
    assert s["semantic"]["mrr"] >= s["keyword"]["mrr"] - 0.1


def test_semantic_quality_floor(evaluation):
    """Loose bounds: they catch a broken model, floor or index, not small drift."""
    overall = evaluation["summary"]["overall"]["semantic"]
    assert overall["mrr"] >= 0.8
    assert overall["recall@5"] >= 0.8


def test_off_topic_queries_return_nothing(evaluation):
    ab = evaluation["abstention"]["semantic"]
    assert ab["correctly_empty"] == ab["queries"]
