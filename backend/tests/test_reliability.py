"""Phase B: degradation, logging, keyword tokenisation, health."""

import sqlite3

import pytest
from sqlalchemy.exc import OperationalError

from app.services import embedding_service
from app.services.embedding_service import EmbeddingUnavailable
from app.services.search_service import _keyword_terms, _escape_like


def _rows(db_path, sql, *args):
    con = sqlite3.connect(db_path)
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def _first_product(client):
    return client.get("/api/search", params={"q": "a", "min_similarity": 0, "limit": 1}).json()["results"][0]["product"]


# ---------- keyword tokenisation ----------

def test_terms_drop_stopwords():
    assert _keyword_terms("warm winter jacket for men") == ["warm", "winter", "jacket", "men"]


def test_terms_fall_back_to_raw_phrase():
    assert _keyword_terms("the a") == ["the a"]


def test_like_escape():
    assert _escape_like("50%_off") == r"50\%\_off"


def test_multiword_query_matches_non_adjacent_words(client):
    """The old whole-phrase ILIKE found nothing for this; AND-of-terms does."""
    name = _first_product(client)["name"]
    words = [w for w in name.split() if len(w) > 2]
    if len(words) < 2:
        pytest.skip("product name too short for a two-word query")
    q = f"{words[-1]} {words[0]}"  # reversed order can never be a substring
    body = client.get("/api/search/keyword", params={"q": q, "limit": 100}).json()
    assert name in {r["product"]["name"] for r in body["results"]}


def test_keyword_requires_all_terms(client):
    body = client.get("/api/search/keyword", params={"q": "laptop zzzzqqqq"}).json()
    assert body["total"] == 0


def test_percent_in_query_is_literal_not_a_wildcard(client):
    """'%' matches only products that contain a literal percent sign (5 in the data), not everything."""
    total = client.get("/api/search/keyword", params={"q": "%", "limit": 100}).json()
    assert 0 < total["total"] < 72
    for r in total["results"]:
        p = r["product"]
        assert "%" in f'{p["name"]} {p["description"]} {p["brand"]}'


# ---------- degradation ----------

def test_missing_embeddings_fall_back_to_keyword(client, monkeypatch):
    async def boom(*a, **k):
        raise EmbeddingUnavailable("no model")
    monkeypatch.setattr("app.api.search.semantic_search", boom)
    r = client.get("/api/search", params={"q": "laptop fallbackcheck"})
    assert r.status_code == 200
    assert r.json()["search_type"] == "keyword"


def test_degraded_answer_is_not_cached(client, monkeypatch):
    q = "coffee mug degraded-cache-check"
    async def boom(*a, **k):
        raise EmbeddingUnavailable("no model")
    with monkeypatch.context() as m:
        m.setattr("app.api.search.semantic_search", boom)
        assert client.get("/api/search", params={"q": q}).json()["search_type"] == "keyword"
    assert client.get("/api/search", params={"q": q}).json()["search_type"] == "semantic"


def test_database_error_is_503_not_a_fake_fallback(client, monkeypatch):
    async def boom(*a, **k):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))
    monkeypatch.setattr("app.api.search.semantic_search", boom)
    r = client.get("/api/search", params={"q": "db down check"})
    assert r.status_code == 503
    assert r.json()["detail"] == "database unavailable"


def test_failed_model_load_is_fast_and_cached(monkeypatch):
    calls = []

    def failing(*a, **k):
        calls.append(1)
        raise OSError("hub unreachable")

    monkeypatch.setattr(embedding_service, "_model", None)
    monkeypatch.setattr(embedding_service, "_failed_at", None)
    monkeypatch.setattr(embedding_service, "SentenceTransformer", failing)
    with pytest.raises(EmbeddingUnavailable):
        embedding_service.get_model()
    n = len(calls)
    with pytest.raises(EmbeddingUnavailable):
        embedding_service.get_model()  # inside the cool-down: must not retry
    assert len(calls) == n
    assert embedding_service.embedding_status() == "unavailable"


def test_model_tries_local_cache_before_network(monkeypatch):
    seen = []

    def fake(name, **kw):
        seen.append(kw)
        if kw.get("local_files_only"):
            return object()
        raise AssertionError("network used although cache loaded")

    monkeypatch.setattr(embedding_service, "_model", None)
    monkeypatch.setattr(embedding_service, "_failed_at", None)
    monkeypatch.setattr(embedding_service, "SentenceTransformer", fake)
    embedding_service.get_model()
    assert seen == [{"local_files_only": True}]


# ---------- logging & clicks ----------

def test_every_search_is_logged_including_cache_hits(client, db_path):
    q = "unique-log-probe tent"
    before = _rows(db_path, "SELECT count(*) FROM search_logs WHERE query_text=?", q)[0][0]
    client.get("/api/search", params={"q": q})
    client.get("/api/search", params={"q": q})  # served from cache
    after = _rows(db_path, "SELECT count(*) FROM search_logs WHERE query_text=?", q)[0][0]
    assert after - before == 2


def test_click_is_recorded(client, db_path):
    pid = _first_product(client)["product_id"]
    r = client.post("/api/click", json={"query": "click-probe", "product_id": pid})
    assert r.status_code == 200
    rows = _rows(db_path, "SELECT clicked_product_id FROM search_logs WHERE query_text='click-probe'")
    assert len(rows) == 1 and rows[0][0].replace("-", "") == pid.replace("-", "")


def test_click_on_unknown_product_404(client):
    r = client.post("/api/click", json={"query": "x", "product_id": "00000000-0000-4000-8000-000000000000"})
    assert r.status_code == 404


def test_click_validates_body(client):
    assert client.post("/api/click", json={"query": "", "product_id": "nope"}).status_code == 422


# ---------- health ----------

def test_health_reports_components(client):
    body = client.get("/health").json()
    assert body["database"] == "ok"
    assert body["embeddings"] in {"ready", "loading"}
    assert body["status"] in {"ok", "degraded"}
