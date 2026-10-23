"""FR8: click-popularity re-ranking. Off by default; never alters reported scores."""

import pytest

from app.api import search as search_api
from app.config import get_settings

QUERY = {"q": "wireless audio gear", "min_similarity": 0, "limit": 6}


def _ranking(client):
    search_api._search_cache.clear()
    body = client.get("/api/search", params=QUERY).json()
    return [(r["product"]["product_id"], r["score"]) for r in body["results"]]


def test_default_is_off():
    assert get_settings().click_boost_weight == 0.0


def test_clicks_alone_do_not_change_ranking_when_off(client):
    before = _ranking(client)
    victim = before[-1][0]
    for _ in range(5):
        client.post("/api/click", json={"query": QUERY["q"], "product_id": victim})
    assert [pid for pid, _ in _ranking(client)] == [pid for pid, _ in before]


def test_boost_promotes_clicked_product_without_touching_scores(client, monkeypatch):
    base = _ranking(client)
    victim = base[-1][0]
    for _ in range(40):
        client.post("/api/click", json={"query": QUERY["q"], "product_id": victim})

    monkeypatch.setattr(get_settings(), "click_boost_weight", 1.0)
    boosted = _ranking(client)

    assert boosted[0][0] == victim, "a heavily clicked product should rise to the top"
    assert dict(boosted) == dict(base), "scores must stay the raw similarity"
    assert sorted(pid for pid, _ in boosted) == sorted(pid for pid, _ in base), "same products, new order"


def test_turning_the_boost_off_restores_the_original_order(client, monkeypatch):
    with monkeypatch.context() as m:
        m.setattr(get_settings(), "click_boost_weight", 1.0)
        _ranking(client)
    search_api._search_cache.clear()
    restored = _ranking(client)
    assert [pid for pid, _ in restored] == sorted((pid for pid, _ in restored), key=lambda p: -dict(restored)[p])


def test_boost_with_no_clicks_is_a_no_op(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "click_boost_weight", 5.0)
    search_api._search_cache.clear()
    body = client.get("/api/search", params={"q": "kitchen cookware", "min_similarity": 0, "limit": 6}).json()
    scores = [r["score"] for r in body["results"]]
    assert scores == sorted(scores, reverse=True)
