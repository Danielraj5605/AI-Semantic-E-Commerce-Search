"""Validate the browser's hand-written RDF serialisers with an independent parser.

frontend/src/rdf.js is run under Node over the whole catalogue; the output is then
parsed by rdflib (not our code) and compared:

  * every syntax must parse                      -> the RDF is valid
  * Turtle, RDF/XML, JSON-LD must be isomorphic  -> they describe one graph
  * that graph must equal the Python mapping     -> two implementations of the
                                                    Unit-4 rules agree

If any of these fail, the interface is publishing RDF that does not mean what it says.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from rdflib import Graph
from rdflib.compare import graph_diff, isomorphic, to_isomorphic

from app.services.rdf_service import product_graph

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "frontend" / "scripts" / "export-graphs.mjs"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


@pytest.fixture(scope="module")
def products(client):
    body = client.get("/api/search", params={"q": "product", "min_similarity": 0, "limit": 100}).json()
    return [r["product"] for r in body["results"]]


@pytest.fixture(scope="module")
def graphs(products, tmp_path_factory):
    work = tmp_path_factory.mktemp("rdf")
    (work / "products.json").write_text(json.dumps(products), encoding="utf-8")
    run = subprocess.run(["node", str(SCRIPT), str(work / "products.json"), str(work / "out")],
                         capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    out = work / "out"
    return {
        "turtle": Graph().parse(out / "all.ttl", format="turtle"),
        "rdfxml": Graph().parse(out / "all.rdf", format="xml"),
        "jsonld": Graph().parse(out / "all.jsonld", format="json-ld"),
    }


def _explain(a, b, limit=5):
    _, only_a, only_b = graph_diff(to_isomorphic(a), to_isomorphic(b))
    return f"\nonly in first: {sorted(only_a)[:limit]}\nonly in second: {sorted(only_b)[:limit]}"


def test_catalogue_is_nonempty(products):
    assert len(products) >= 50


@pytest.mark.parametrize("syntax", ["turtle", "rdfxml", "jsonld"])
def test_every_syntax_parses_and_is_nonempty(graphs, syntax):
    assert len(graphs[syntax]) > 1000


def test_turtle_equals_rdfxml(graphs):
    assert isomorphic(graphs["turtle"], graphs["rdfxml"]), _explain(graphs["turtle"], graphs["rdfxml"])


def test_turtle_equals_jsonld(graphs):
    assert isomorphic(graphs["turtle"], graphs["jsonld"]), _explain(graphs["turtle"], graphs["jsonld"])


def test_browser_graph_equals_backend_graph(graphs, products):
    """rdf.js (JavaScript) and rdf_service.py (rdflib) implement the same mapping."""
    backend = Graph()
    for p in products:
        backend += product_graph(p)
    assert isomorphic(graphs["turtle"], backend), _explain(graphs["turtle"], backend)
