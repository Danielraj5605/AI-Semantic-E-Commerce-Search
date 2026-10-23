"""The upper layers: ontology (OWL), logic (reasoner), proof, trust."""

from decimal import Decimal

import pytest
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, XSD

from app.semantics import ontology as onto
from app.semantics import proof, trust
from app.semantics.reasoner import Reasoner
from app.services import rdf_service
from app.services.rdf_service import CAT, SCHEMA

CATS = [
    {"name": "Electronics", "parent": None},
    {"name": "Laptops", "parent": "Electronics"},
    {"name": "Audio", "parent": "Electronics"},
    {"name": "Clothing", "parent": None},
    {"name": "Footwear", "parent": "Clothing"},
    {"name": "Books", "parent": None},
]
NIL = "00000000-0000-4000-8000-000000000000"


def product(**over):
    base = {"product_id": "p1", "name": "Aero Laptop", "category_name": "Laptops", "brand": "Aero",
            "price": 899.99, "stock_quantity": 3, "rating_avg": 4.6}
    return {**base, **over}


@pytest.fixture(scope="module")
def reasoner():
    return Reasoner(onto.build_ontology(CATS))


def run(reasoner, **over):
    return reasoner.entail(rdf_service.product_graph(product(**over)))


def types_of(ent, pid="p1"):
    return {str(t).rsplit("#", 1)[-1] for t in ent.graph.objects(rdf_service.product_uri(pid), RDF.type)}


# ---------- OWL ----------

def test_ontology_declares_every_category_as_a_class_with_its_parent():
    g = onto.build_ontology(CATS)
    for c in CATS:
        assert (CAT[rdf_service.local_name(c["name"])], RDF.type, OWL.Class) in g
    assert (CAT.Laptops, RDFS.subClassOf, CAT.Electronics) in g
    assert (CAT.Electronics, RDFS.subClassOf, SCHEMA.Product) in g


def test_siblings_at_the_top_are_disjoint_but_children_inherit_nothing_directly():
    g = onto.build_ontology(CATS)
    assert (CAT.Books, OWL.disjointWith, CAT.Clothing) in g or (CAT.Clothing, OWL.disjointWith, CAT.Books) in g
    assert (CAT.Laptops, OWL.disjointWith, CAT.Audio) not in g


def test_ontology_serialises_and_reparses_to_the_same_graph():
    from rdflib.compare import isomorphic
    g = onto.build_ontology(CATS)
    for fmt in ("turtle", "xml", "json-ld"):
        assert isomorphic(g, Graph().parse(data=g.serialize(format=fmt), format=fmt)), fmt


def test_defined_classes_round_trip_through_the_owl_encoding(reasoner):
    parsed = {str(c).rsplit("#", 1)[1]: (path, test) for c, path, test, _ in reasoner.defined}
    assert set(parsed) == {d.name for d in onto.DEFINED_CLASSES}
    assert parsed["Premium"] == ((SCHEMA.offers, SCHEMA.price), ("min", Decimal("200")))
    assert parsed["InStockProduct"][1] == ("value", SCHEMA.InStock)


def test_restrictions_are_read_back(reasoner):
    kinds = {(str(c).rsplit("/", 1)[1], str(p).rsplit("/", 1)[1], k, n) for c, p, k, n, _ in reasoner.restrictions}
    assert ("Product", "name", "cardinality", 1) in kinds
    assert ("Product", "brand", "maxCardinality", 1) in kinds


# ---------- Logic ----------

def test_a_laptop_is_inferred_to_be_electronics_and_a_catalogue_thing(reasoner):
    assert {"Laptops", "Electronics", "CatalogueThing"} <= types_of(run(reasoner))


def test_subclass_transitivity_is_derived_and_recorded(reasoner):
    assert (CAT.Laptops, RDFS.subClassOf, CAT.CatalogueThing) in reasoner.derived
    assert reasoner.derived[(CAT.Laptops, RDFS.subClassOf, CAT.CatalogueThing)].rule == "scm-sco"


def test_inverse_property_links_brand_back_to_product(reasoner):
    ent = run(reasoner)
    brand = URIRef(f"{rdf_service._ex()}brand/aero")
    assert (brand, CAT.brandOf, rdf_service.product_uri("p1")) in ent.graph
    assert ent.derived[(brand, CAT.brandOf, rdf_service.product_uri("p1"))].rule == "prp-inv"


@pytest.mark.parametrize("price,expected", [(199.99, False), (200, True), (200.01, True)])
def test_premium_boundary(reasoner, price, expected):
    assert ("Premium" in types_of(run(reasoner, price=price))) is expected


@pytest.mark.parametrize("rating,expected", [(4.4, False), (4.5, True), (4.8, True)])
def test_top_rated_boundary(reasoner, rating, expected):
    assert ("TopRated" in types_of(run(reasoner, rating_avg=rating))) is expected


@pytest.mark.parametrize("stock,expected", [(0, False), (1, True)])
def test_in_stock_is_computed_not_stored(reasoner, stock, expected):
    assert ("InStockProduct" in types_of(run(reasoner, stock_quantity=stock))) is expected


def test_a_brand_is_not_mistaken_for_a_product(reasoner):
    """schema:name is shared by products and brands, so its domain must not be Product."""
    ent = run(reasoner)
    brand = URIRef(f"{rdf_service._ex()}brand/aero")
    assert (brand, RDF.type, SCHEMA.Product) not in ent.graph
    assert (brand, RDF.type, SCHEMA.Brand) in ent.graph


def test_a_conforming_product_has_no_violations(reasoner):
    assert run(reasoner).violations == []


def test_asserted_data_is_never_modified(reasoner):
    data = rdf_service.product_graph(product())
    before = set(data)
    reasoner.entail(data)
    assert set(data) == before


def test_entailment_is_idempotent(reasoner):
    ent = run(reasoner)
    again = reasoner.entail(ent.asserted)
    assert set(again.graph) == set(ent.graph)


def test_matches_an_independent_sparql_oracle(reasoner):
    """rdflib's property-path evaluation computes the same class closure we do."""
    ent = run(reasoner)
    subject = rdf_service.product_uri("p1")
    rows = reasoner.ontology + ent.asserted
    oracle = {str(r[0]) for r in rows.query(
        "SELECT DISTINCT ?c WHERE { ?s a/rdfs:subClassOf* ?c . FILTER(isIRI(?c)) }",
        initNs={"rdfs": RDFS}, initBindings={"s": subject})}
    defined = {str(CAT[d.name]) for d in onto.DEFINED_CLASSES}
    ours = {str(t) for t in ent.graph.objects(subject, RDF.type)} - defined
    assert ours == oracle


# ---------- Violations ----------

def _rules(ent):
    return {v.rule for v in ent.violations}


def test_disjoint_categories_are_inconsistent(reasoner):
    g = rdf_service.product_graph(product())
    g.add((rdf_service.product_uri("p1"), RDF.type, CAT.Books))
    ent = reasoner.entail(g)
    assert "cax-dw" in _rules(ent)


def test_sibling_subcategories_are_not_disjoint(reasoner):
    g = rdf_service.product_graph(product())
    g.add((rdf_service.product_uri("p1"), RDF.type, CAT.Audio))
    assert "cax-dw" not in _rules(reasoner.entail(g))


def test_missing_name_violates_cardinality(reasoner):
    assert "cls-card" in _rules(run(reasoner, name=None))


def test_two_brands_violate_max_cardinality(reasoner):
    g = rdf_service.product_graph(product())
    g.add((rdf_service.product_uri("p1"), SCHEMA.brand, URIRef("http://example.org/catalog/brand/other")))
    assert "cls-card" in _rules(reasoner.entail(g))


def test_negative_price_and_out_of_range_rating_are_caught(reasoner):
    assert "dt-bound" in _rules(run(reasoner, price=-1))
    g = rdf_service.product_graph(product())
    rating = g.value(rdf_service.product_uri("p1"), SCHEMA.aggregateRating)
    g.set((rating, SCHEMA.ratingValue, Literal("7.5", datatype=XSD.decimal)))
    assert "dt-bound" in _rules(reasoner.entail(g))


def test_wrong_datatype_is_caught(reasoner):
    g = rdf_service.product_graph(product())
    offer = g.value(rdf_service.product_uri("p1"), SCHEMA.offers)
    g.set((offer, SCHEMA.price, Literal("cheap")))
    assert "dt-range" in _rules(reasoner.entail(g))


def test_undeclared_class_is_caught(reasoner):
    assert "cls-decl" in _rules(run(reasoner, category_name="Gadgets"))


# ---------- Proof ----------

def test_every_derived_fact_about_the_product_has_a_grounded_proof(reasoner):
    ent = run(reasoner)
    items = proof.proofs_for(ent)
    assert len(items) >= 5
    for item in items:
        leaves = proof.leaves(item["proof"])
        assert leaves and all(leaf["kind"] in ("asserted", "axiom") for leaf in leaves), item["conclusion"]


def test_proof_of_a_superclass_walks_the_subclass_chain(reasoner):
    ent = run(reasoner)
    tree = proof.explain(ent, (rdf_service.product_uri("p1"), RDF.type, CAT.CatalogueThing))
    assert tree["rule"] in ("cax-sco", "prp-dom")  # several valid derivations; the first found is kept
    tree = proof.explain(ent, (rdf_service.product_uri("p1"), RDF.type, CAT.Electronics))
    text = proof.render(tree)
    assert tree["rule"] == "cax-sco" and "cat:Laptops" in text and "rdfs:subClassOf cat:Electronics" in text


def test_a_defined_class_proof_names_the_value_that_qualified(reasoner):
    ent = run(reasoner)
    tree = proof.explain(ent, (rdf_service.product_uri("p1"), RDF.type, CAT.Premium))
    assert tree["rule"] == "cls-def" and "899.99" in tree["note"]


def test_an_asserted_fact_is_a_leaf_not_a_derivation(reasoner):
    ent = run(reasoner)
    leaf = proof.explain(ent, (rdf_service.product_uri("p1"), RDF.type, CAT.Laptops))
    assert leaf["kind"] == "asserted"


# ---------- Trust: integrity ----------

def test_digest_ignores_blank_node_labels_but_sees_content():
    g1 = rdf_service.product_graph(product())
    g2 = Graph().parse(data=g1.serialize(format="turtle"), format="turtle")  # fresh bnode ids
    assert trust.digest(g1) == trust.digest(g2)
    g2.add((rdf_service.product_uri("p1"), SCHEMA.name, Literal("Tampered", lang="en")))
    assert trust.digest(g1) != trust.digest(g2)


def test_signature_verifies_and_detects_tampering():
    g = rdf_service.product_graph(product())
    sig = trust.sign(trust.digest(g))
    assert trust.verify(g, sig)[0]
    g.set((rdf_service.product_uri("p1"), SCHEMA.name, Literal("Tampered", lang="en")))
    assert not trust.verify(g, sig)[0]
    assert not trust.verify(rdf_service.product_graph(product()), "0" * 64)[0]


def test_provenance_records_source_activity_agent_and_each_inference(reasoner):
    ent = run(reasoner)
    subject = rdf_service.product_uri("p1")
    prov = trust.provenance_graph(product(), ent, subject)
    from rdflib.namespace import PROV
    assert (subject, PROV.wasDerivedFrom, URIRef(f"{rdf_service._ex()}table/products")) in prov
    statements = list(prov.subjects(RDF.type, RDF.Statement))
    assert len(statements) == len(ent.about_data())
    assert all(prov.value(s, CAT.derivedByRule) for s in statements)


# ---------- Trust: calibration ----------

def test_pav_never_lets_confidence_fall_as_score_rises():
    out = trust.pool_adjacent_violators([(1, 10), (3, 10), (1, 10), (9, 10)])
    assert out == sorted(out)


def test_pav_pools_a_violation_into_the_weighted_mean():
    out = trust.pool_adjacent_violators([(5, 10), (2, 10)])
    assert out == [0.35, 0.35]


CAL = {"bins": [{"lo": 0.25, "hi": 0.5, "relevant": 1, "n": 10, "precision": 0.1},
                {"lo": 0.5, "hi": 1.0, "relevant": 9, "n": 10, "precision": 0.9}]}


def test_calibrated_confidence_reads_the_right_bin():
    assert trust.calibrated_confidence(0.3, CAL)["confidence"] == 0.1
    assert trust.calibrated_confidence(0.5, CAL)["confidence"] == 0.9
    assert trust.calibrated_confidence(0.99, CAL)["confidence"] == 0.9
    assert trust.calibrated_confidence(None, CAL)["confidence"] is None


# ---------- API (real catalogue) ----------

def _first(client):
    return client.get("/api/search", params={"q": "laptop", "min_similarity": 0, "limit": 1}).json()["results"][0]["product"]


def test_whole_catalogue_conforms_to_its_ontology(client):
    r = client.get("/api/ontology/validate").json()
    assert r["conforms"], r["violations"][:3]
    assert r["products_checked"] >= 70
    assert r["by_rule"]["cax-sco"] > r["products_checked"]


def test_ontology_json_and_rdf(client):
    j = client.get("/api/ontology").json()
    names = {c["qname"] for c in j["classes"]}
    assert {"cat:Electronics", "cat:Laptops", "cat:Premium"} <= names
    assert any(c["qname"] == "cat:Laptops" and "cat:Electronics" in c["parents"] for c in j["classes"])
    r = client.get("/api/ontology", headers={"Accept": "text/turtle"})
    assert r.headers["content-type"].startswith("text/turtle")
    g = Graph().parse(data=r.text, format="turtle")
    assert (CAT.Laptops, RDFS.subClassOf, CAT.Electronics) in g


def test_inferences_endpoint_lists_rules_and_serialises_the_closure(client):
    p = _first(client)
    body = client.get(f"/api/product/{p['product_id']}/inferences").json()
    assert body["consistent"] and body["asserted"] > 10
    assert {"cax-sco", "prp-inv"} <= {i["rule"] for i in body["inferred"]}
    ttl = client.get(f"/api/product/{p['product_id']}/inferences?format=ttl")
    g = Graph().parse(data=ttl.text, format="turtle")
    assert (rdf_service.product_uri(p["product_id"]), RDF.type, CAT.CatalogueThing) in g


def test_proof_endpoint(client):
    p = _first(client)
    body = client.get(f"/api/product/{p['product_id']}/proof").json()
    assert body["proofs"]
    top = next(x for x in body["proofs"] if x["conclusion"].endswith("cat:CatalogueThing"))
    assert top["depth"] >= 2 and "cax-sco" in top["text"]
    inferred = client.get(f"/api/product/{p['product_id']}/inferences").json()["inferred"]
    assert len(body["proofs"]) == len(inferred), "every inference has a proof"


def test_provenance_sign_verify_and_tamper(client):
    p = _first(client)
    pid = p["product_id"]
    prov = client.get(f"/api/product/{pid}/provenance").json()
    assert len(prov["digest"]) == 64 and prov["signature_algorithm"] == "HMAC-SHA256"

    ok = client.post("/api/verify", json={"turtle": prov["graph_turtle"], "signature": prov["signature"], "product_id": pid}).json()
    assert ok["signature_valid"] and ok["matches_catalogue"]

    forged = prov["graph_turtle"].replace(p["name"], "Something Else Entirely")
    bad = client.post("/api/verify", json={"turtle": forged, "signature": prov["signature"], "product_id": pid}).json()
    assert not bad["signature_valid"] and not bad["matches_catalogue"]

    assert client.post("/api/verify", json={"turtle": "not turtle {{", "signature": "x"}).status_code == 422


def test_provenance_rdf_has_digest_headers(client):
    p = _first(client)
    r = client.get(f"/api/product/{p['product_id']}/provenance", headers={"Accept": "text/turtle"})
    assert r.headers["x-content-signature"] and len(r.headers["x-content-digest"]) == 64
    assert "prov:wasGeneratedBy" in r.text


def test_calibration_endpoint_is_monotone(client):
    cal = client.get("/api/trust/calibration").json()
    precisions = [b["precision"] for b in cal["bins"]]
    assert precisions == sorted(precisions) and cal["results"] > 50


def test_unknown_product_is_404_on_every_semantic_route(client):
    for path in ("inferences", "proof", "provenance"):
        assert client.get(f"/api/product/{NIL}/{path}").status_code == 404


def test_rules_catalogue(client):
    ids = {r["id"] for r in client.get("/api/logic/rules").json()}
    assert {"cax-sco", "scm-sco", "cls-def", "cax-dw"} <= ids
