"""Phase C: content negotiation, find-similar, admin CRUD."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from rdflib import Graph, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import RDF

from app.services import rdf_service

BACKEND = Path(__file__).resolve().parent.parent
SCHEMA = "http://schema.org/"
ADMIN = {"X-Admin-Token": "test-admin-token"}
NIL = "00000000-0000-4000-8000-000000000000"


def _product(client, q="coffee"):
    return client.get("/api/search", params={"q": q, "min_similarity": 0, "limit": 1}).json()["results"][0]["product"]


# ---------- content negotiation ----------

def test_default_is_json(client):
    p = _product(client)
    r = client.get(f"/api/product/{p['product_id']}")
    assert r.status_code == 200 and r.json()["name"] == p["name"]


@pytest.mark.parametrize("accept,fmt", [
    ("text/turtle", "turtle"),
    ("application/rdf+xml", "xml"),
    ("application/ld+json", "json-ld"),
])
def test_rdf_formats_parse_back_to_the_same_product(client, accept, fmt):
    p = _product(client)
    r = client.get(f"/api/product/{p['product_id']}", headers={"Accept": accept})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(accept)
    assert r.headers["vary"] == "Accept"
    g = Graph().parse(data=r.text, format=fmt)
    subject = rdf_service.product_uri(p["product_id"])
    assert (subject, RDF.type, URIRef(SCHEMA + "Product")) in g
    names = {str(o) for o in g.objects(subject, URIRef(SCHEMA + "name"))}
    assert p["name"] in names


def test_all_three_syntaxes_describe_the_same_graph(client):
    p = _product(client)
    graphs = [
        Graph().parse(data=client.get(f"/api/product/{p['product_id']}", headers={"Accept": a}).text, format=f)
        for a, f in [("text/turtle", "turtle"), ("application/rdf+xml", "xml"), ("application/ld+json", "json-ld")]
    ]
    assert isomorphic(graphs[0], graphs[1])
    assert isomorphic(graphs[0], graphs[2])


def test_graph_is_typed_and_reified(client):
    p = _product(client)
    g = Graph().parse(data=client.get(f"/api/product/{p['product_id']}?format=ttl").text, format="turtle")
    s = rdf_service.product_uri(p["product_id"])
    offer = g.value(s, URIRef(SCHEMA + "offers"))
    price = g.value(offer, URIRef(SCHEMA + "price"))
    assert str(price.datatype).endswith("#decimal")
    assert g.value(offer, RDF.type) == URIRef(SCHEMA + "Offer")


def test_format_param_overrides_accept(client):
    p = _product(client)
    r = client.get(f"/api/product/{p['product_id']}?format=jsonld", headers={"Accept": "text/turtle"})
    assert r.headers["content-type"].startswith("application/ld+json")


def test_unknown_format_is_406(client):
    p = _product(client)
    assert client.get(f"/api/product/{p['product_id']}?format=pdf").status_code == 406


def test_unknown_product_404_in_every_format(client):
    assert client.get(f"/api/product/{NIL}").status_code == 404
    assert client.get(f"/api/product/{NIL}", headers={"Accept": "text/turtle"}).status_code == 404


def test_negotiate_respects_q_values():
    n = rdf_service.negotiate
    assert n("application/rdf+xml;q=0.2, text/turtle;q=0.9") == "text/turtle"
    assert n("application/json, text/turtle;q=0.5") is None
    assert n("*/*") is None and n(None) is None


def test_local_name_and_slug_match_the_frontend():
    assert rdf_service.local_name("Men's Clothing") == "MensClothing"
    assert rdf_service.local_name("Home & Kitchen") == "HomeKitchen"
    assert rdf_service.slug("Northline Co.") == "northline-co"


def test_base_uri_is_configurable(monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "base_uri", "http://localhost:8000/api")
    assert str(rdf_service.product_uri("abc")) == "http://localhost:8000/api/product/abc"


# ---------- find similar ----------

def test_similar_excludes_seed_and_is_ranked(client):
    p = _product(client, "laptop")
    body = client.get(f"/api/product/{p['product_id']}/similar", params={"limit": 5}).json()
    ids = [r["product"]["product_id"] for r in body["results"]]
    assert ids and p["product_id"] not in ids
    scores = [r["score"] for r in body["results"]]
    assert scores == sorted(scores, reverse=True)


def test_similar_prefers_same_kind_of_thing(client):
    p = _product(client, "laptop")
    top = client.get(f"/api/product/{p['product_id']}/similar", params={"limit": 3}).json()["results"]
    assert any(r["product"]["category_name"] == p["category_name"] for r in top)


def test_similar_does_not_need_the_encoder(client, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("encoder used")
    monkeypatch.setattr("app.services.search_service.encode_text", boom)
    p = _product(client, "laptop")
    assert client.get(f"/api/product/{p['product_id']}/similar").status_code == 200


def test_similar_unknown_product_404(client):
    assert client.get(f"/api/product/{NIL}/similar").status_code == 404


# ---------- admin ----------

NEW = {"name": "Zephyr Titanium Pour-Over Kettle", "description": "gooseneck kettle for brewing pour-over coffee",
       "category": "Home & Kitchen", "brand": "Zephyr", "price": 59.5, "stock_quantity": 4, "rating_avg": 4.4}


def test_admin_requires_token(client):
    assert client.post("/api/admin/products", json=NEW).status_code == 401
    assert client.post("/api/admin/products", json=NEW, headers={"X-Admin-Token": "wrong"}).status_code == 401
    assert client.delete(f"/api/admin/products/{NIL}").status_code == 401


def test_admin_disabled_without_token():
    code = (
        "import os; os.environ['ADMIN_TOKEN']=''; os.environ['USE_LOCAL_DB']='true';"
        "from app.main import app; print(any(r.path.startswith('/api/admin') for r in app.routes))"
    )
    out = subprocess.run([sys.executable, "-W", "ignore", "-c", code], cwd=BACKEND,
                         capture_output=True, text=True, env={**os.environ, "HF_HUB_OFFLINE": "1"})
    assert out.stdout.strip().splitlines()[-1] == "False", out.stderr[-500:]


def test_admin_lifecycle_create_update_delete(client):
    before = client.get("/api/search", params={"q": "gooseneck kettle", "limit": 5}).json()
    assert NEW["name"] not in [r["product"]["name"] for r in before["results"]]

    r = client.post("/api/admin/products", json=NEW, headers=ADMIN)
    assert r.status_code == 201 and r.json()["embedding"] == "updated"
    pid = r.json()["product_id"]

    # created -> findable by meaning at once (cache was cleared, vector was written)
    hit = client.get("/api/search", params={"q": "gooseneck kettle", "limit": 5}).json()
    assert hit["results"][0]["product"]["product_id"] == pid
    assert client.get(f"/api/product/{pid}").json()["brand"] == "Zephyr"

    # updated -> re-embedded, so the new meaning is what search sees
    r = client.put(f"/api/admin/products/{pid}", json={
        "name": "Aurora Bluetooth Speaker", "description": "portable wireless speaker",
        "category": "Audio", "brand": "Aurora"}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["embedding"] == "updated"
    moved = client.get("/api/search", params={"q": "portable wireless speaker", "limit": 5}).json()
    assert pid in [x["product"]["product_id"] for x in moved["results"]]
    assert client.get(f"/api/product/{pid}").json()["category_name"] == "Audio"

    # deleted -> gone everywhere
    assert client.delete(f"/api/admin/products/{pid}", headers=ADMIN).status_code == 204
    assert client.get(f"/api/product/{pid}").status_code == 404
    after = client.get("/api/search", params={"q": "portable wireless speaker", "limit": 50, "min_similarity": 0}).json()
    assert pid not in [x["product"]["product_id"] for x in after["results"]]


def test_admin_validation_and_not_found(client):
    assert client.post("/api/admin/products", json={**NEW, "category": "Nope"}, headers=ADMIN).status_code == 422
    assert client.post("/api/admin/products", json={**NEW, "price": -1}, headers=ADMIN).status_code == 422
    assert client.put(f"/api/admin/products/{NIL}", json={"name": "x"}, headers=ADMIN).status_code == 404


def test_admin_write_survives_a_dead_encoder(client, monkeypatch):
    from app.services.embedding_service import EmbeddingUnavailable

    def down(*a, **k):
        raise EmbeddingUnavailable("down")
    monkeypatch.setattr("app.api.admin.encode_text", down)
    r = client.post("/api/admin/products", json={**NEW, "name": "Pending Vector Item"}, headers=ADMIN)
    assert r.status_code == 201 and r.json()["embedding"] == "pending"
    pid = r.json()["product_id"]
    assert client.get(f"/api/product/{pid}/similar").status_code == 404  # no vector yet
    client.delete(f"/api/admin/products/{pid}", headers=ADMIN)
