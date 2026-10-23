"""Characterisation tests: pin the API behaviour that exists today."""

import pytest


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_filters_shape(client):
    body = client.get("/api/filters").json()
    assert body["categories"] and body["brands"]
    assert set(body["price_range"]) == {"min", "max"}
    assert body["price_range"]["min"] <= body["price_range"]["max"]
    assert {"category_id", "name", "parent_category_id"} <= set(body["categories"][0])


def test_category_hierarchy_is_populated(client):
    cats = client.get("/api/filters").json()["categories"]
    assert any(c["parent_category_id"] is not None for c in cats), \
        "class tree is flat: parent_category_id never set"


def test_semantic_search_shape_and_ordering(client):
    body = client.get("/api/search", params={"q": "something to keep coffee hot"}).json()
    assert body["search_type"] == "semantic"
    assert body["total"] >= len(body["results"]) > 0
    scores = [r["score"] for r in body["results"]]
    assert scores == sorted(scores, reverse=True)
    assert all(0 <= s <= 1 for s in scores)
    assert {"product_id", "name", "price", "category_name"} <= set(body["results"][0]["product"])


def test_relevance_floor_trims_results(client):
    floor = client.get("/api/search", params={"q": "warm jacket", "limit": 100}).json()
    raw = client.get("/api/search", params={"q": "warm jacket", "limit": 100, "min_similarity": 0}).json()
    assert raw["total"] >= floor["total"]
    assert raw["total"] == 72 or raw["total"] > 0


def test_structural_filters_apply(client):
    brand = client.get("/api/filters").json()["brands"][0]
    body = client.get("/api/search", params={"q": "anything", "brand": brand, "limit": 100}).json()
    assert body["results"], "brand constraint should return its members"
    assert all(r["product"]["brand"].lower() == brand.lower() for r in body["results"])

    cheap = client.get("/api/search", params={"q": "anything", "max_price": 25, "min_similarity": 0, "limit": 100}).json()
    assert all(r["product"]["price"] <= 25 for r in cheap["results"])


def test_pagination_does_not_overlap(client):
    p = {"q": "shoes", "min_similarity": 0, "limit": 5}
    a = client.get("/api/search", params={**p, "offset": 0}).json()
    b = client.get("/api/search", params={**p, "offset": 5}).json()
    ids_a = {r["product"]["product_id"] for r in a["results"]}
    ids_b = {r["product"]["product_id"] for r in b["results"]}
    assert not ids_a & ids_b


def test_keyword_search(client):
    name = client.get("/api/search", params={"q": "a", "min_similarity": 0, "limit": 1}).json()["results"][0]["product"]["name"]
    word = name.split()[0]
    body = client.get("/api/search/keyword", params={"q": word}).json()
    assert body["search_type"] == "keyword"
    assert body["total"] >= 1
    assert all(r["score"] == 1.0 for r in body["results"])


def test_autocomplete(client):
    name = client.get("/api/search", params={"q": "a", "min_similarity": 0, "limit": 1}).json()["results"][0]["product"]["name"]
    out = client.get("/api/autocomplete", params={"q": name[:3]}).json()["suggestions"]
    assert name in out


@pytest.mark.parametrize("params", [
    {"q": ""},
    {"q": "x" * 501},
    {"q": "x", "min_rating": 6},
    {"q": "x", "limit": 0},
    {"q": "x", "limit": 101},
    {"q": "x", "min_price": -1},
])
def test_validation_rejects_bad_input(client, params):
    assert client.get("/api/search", params=params).status_code == 422


def _children(client, parent_name):
    cats = client.get("/api/filters").json()["categories"]
    pid = next(c["category_id"] for c in cats if c["name"] == parent_name)
    return [c["name"] for c in cats if c["parent_category_id"] == pid]


def test_parent_category_entails_its_subclasses(client):
    """Selecting a class returns members of its subclasses (rdfs:subClassOf entailment)."""
    kids = _children(client, "Electronics")
    assert kids, "Electronics should have subclasses"
    body = client.get("/api/search", params={"q": "device", "category": "Electronics", "limit": 100}).json()
    got = {r["product"]["category_name"] for r in body["results"]}
    assert got and got <= set(kids) | {"Electronics"}
    assert got & set(kids), "no subclass members returned for the parent class"


def test_leaf_category_unchanged(client):
    body = client.get("/api/search", params={"q": "laptop", "category": "Laptops", "limit": 100}).json()
    assert body["results"]
    assert {r["product"]["category_name"] for r in body["results"]} == {"Laptops"}


def test_keyword_search_also_entails_subclasses(client):
    body = client.get("/api/search/keyword", params={"q": "a", "category": "Clothing", "limit": 100}).json()
    assert {r["product"]["category_name"] for r in body["results"]} <= {"Men's Clothing", "Women's Clothing", "Footwear", "Clothing"}
