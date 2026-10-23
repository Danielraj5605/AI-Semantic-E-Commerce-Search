"""The catalogue ontology, built as real OWL axioms (Unit 2).

Everything here is data, so the ontology document, the reasoner and the UI all
read one source:

  * the class tree comes from the `categories` table (rdfs:subClassOf),
  * sibling top-level categories are declared owl:disjointWith,
  * properties carry rdfs:domain / rdfs:range and inverses,
  * cardinality restrictions say what a well-formed product looks like,
  * "defined classes" (TopRated, Premium, InStockProduct) are owl:equivalentClass
    to a property restriction, so membership is *inferred*, never stored.

The vocabulary used is the OWL 2 RL-friendly subset: every construct below can be
applied by the rule-based reasoner in reasoner.py. This is not OWL DL; there is
no open-world satisfiability checking, and the docs say so.
"""

from dataclasses import dataclass
from decimal import Decimal

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, XSD

from app.services.rdf_service import CAT, SCHEMA, local_name

ONTOLOGY_IRI = URIRef("http://example.org/ontology/catalog")
ROOT = CAT.CatalogueThing


@dataclass(frozen=True)
class DefinedClass:
    """A class whose members are computed from a property path.

    path is the chain of properties from the product to the tested value, and
    test is ("min", Decimal) for ">= threshold" or ("value", URIRef) for a
    specific resource. In OWL this is
        C owl:equivalentClass [ owl:intersectionOf ( schema:Product
            [ a owl:Restriction ; owl:onProperty p1 ; owl:someValuesFrom [ ... ] ] ) ]
    with a datatype restriction (xsd:minInclusive) or owl:hasValue at the end.
    """

    name: str
    label: str
    comment: str
    path: tuple
    test: tuple


DEFINED_CLASSES = (
    DefinedClass(
        "TopRated", "Top rated", "Average rating of 4.5 or more.",
        (SCHEMA.aggregateRating, SCHEMA.ratingValue), ("min", Decimal("4.5")),
    ),
    DefinedClass(
        "Premium", "Premium", "Priced at 200 or more.",
        (SCHEMA.offers, SCHEMA.price), ("min", Decimal("200")),
    ),
    DefinedClass(
        "InStockProduct", "In stock", "Offered with availability schema:InStock.",
        (SCHEMA.offers, SCHEMA.availability), ("value", SCHEMA.InStock),
    ),
)

# property, kind, domain, range
PROPERTIES = (
    # schema:name is also used on brands, so its domain is the root class, not Product
    (SCHEMA.name, "datatype", ROOT, RDFS.Literal),
    (SCHEMA.description, "datatype", SCHEMA.Product, RDFS.Literal),
    (SCHEMA.brand, "object", SCHEMA.Product, SCHEMA.Brand),
    (SCHEMA.offers, "object", SCHEMA.Product, SCHEMA.Offer),
    (SCHEMA.aggregateRating, "object", SCHEMA.Product, SCHEMA.AggregateRating),
    (SCHEMA.price, "datatype", SCHEMA.Offer, XSD.decimal),
    (SCHEMA.ratingValue, "datatype", SCHEMA.AggregateRating, XSD.decimal),
    (SCHEMA.bestRating, "datatype", SCHEMA.AggregateRating, XSD.decimal),
    (DCTERMS.created, "datatype", SCHEMA.Product, XSD.dateTime),
    (CAT.similarityScore, "datatype", SCHEMA.Product, XSD.double),
    (CAT.brandOf, "object", SCHEMA.Brand, SCHEMA.Product),
)

INVERSES = ((CAT.brandOf, SCHEMA.brand),)

# class, property, kind, n
RESTRICTIONS = (
    (SCHEMA.Product, SCHEMA.name, "cardinality", 1),
    (SCHEMA.Product, SCHEMA.brand, "maxCardinality", 1),
    (SCHEMA.Product, SCHEMA.offers, "maxCardinality", 1),
    (SCHEMA.Product, SCHEMA.aggregateRating, "maxCardinality", 1),
    (SCHEMA.Offer, SCHEMA.price, "cardinality", 1),
    (SCHEMA.AggregateRating, SCHEMA.ratingValue, "cardinality", 1),
)

# (property, bound) pairs that must hold on every instance: value in [lo, hi].
RANGE_BOUNDS = (
    (SCHEMA.price, Decimal("0"), None),
    (SCHEMA.ratingValue, Decimal("0"), Decimal("5")),
)


def _lexical(value: Decimal) -> str:
    """Always carry a decimal point: Turtle would otherwise write 200 and re-read it as an integer."""
    text = str(value)
    return text if "." in text else text + ".0"


def class_iri(name: str) -> URIRef:
    return CAT[local_name(name)]


def _restriction(g: Graph, prop, kind: str, n: int) -> BNode:
    r = BNode()
    g.add((r, RDF.type, OWL.Restriction))
    g.add((r, OWL.onProperty, prop))
    g.add((r, getattr(OWL, kind), Literal(n, datatype=XSD.nonNegativeInteger)))
    return r


def _defined_class(g: Graph, d: DefinedClass) -> None:
    kind, arg = d.test
    # innermost: the test on the last property of the path
    if kind == "min":
        facet = BNode()
        g.add((facet, XSD.minInclusive, Literal(_lexical(arg), datatype=XSD.decimal, normalize=False)))
        dr, lst = BNode(), BNode()
        g.add((dr, RDF.type, RDFS.Datatype))
        g.add((dr, OWL.onDatatype, XSD.decimal))
        Collection(g, lst, [facet])
        g.add((dr, OWL.withRestrictions, lst))
        inner = BNode()
        g.add((inner, RDF.type, OWL.Restriction))
        g.add((inner, OWL.onProperty, d.path[-1]))
        g.add((inner, OWL.someValuesFrom, dr))
    else:
        inner = BNode()
        g.add((inner, RDF.type, OWL.Restriction))
        g.add((inner, OWL.onProperty, d.path[-1]))
        g.add((inner, OWL.hasValue, arg))
    # wrap the remaining path outward
    for prop in reversed(d.path[:-1]):
        outer = BNode()
        g.add((outer, RDF.type, OWL.Restriction))
        g.add((outer, OWL.onProperty, prop))
        g.add((outer, OWL.someValuesFrom, inner))
        inner = outer

    cls = CAT[d.name]
    g.add((cls, RDF.type, OWL.Class))
    g.add((cls, RDFS.label, Literal(d.label, lang="en")))
    g.add((cls, RDFS.comment, Literal(d.comment, lang="en")))
    g.add((cls, RDFS.subClassOf, ROOT))
    inter, lst = BNode(), BNode()
    g.add((inter, RDF.type, OWL.Class))
    Collection(g, lst, [SCHEMA.Product, inner])
    g.add((inter, OWL.intersectionOf, lst))
    g.add((cls, OWL.equivalentClass, inter))


def build_ontology(categories: list[dict]) -> Graph:
    """categories: [{"name": str, "parent": str | None}, ...]"""
    g = Graph()
    for prefix, ns in (
        ("schema", SCHEMA), ("cat", CAT), ("owl", OWL), ("rdfs", RDFS),
        ("xsd", XSD), ("dcterms", DCTERMS),
    ):
        g.bind(prefix, ns, override=True, replace=True)

    g.add((ONTOLOGY_IRI, RDF.type, OWL.Ontology))
    g.add((ONTOLOGY_IRI, DCTERMS.title, Literal("CatalogueGraph product ontology", lang="en")))
    g.add((ONTOLOGY_IRI, OWL.versionInfo, Literal("1.0")))

    g.add((ROOT, RDF.type, OWL.Class))
    g.add((ROOT, RDFS.label, Literal("Catalogue thing", lang="en")))
    for c in (SCHEMA.Product, SCHEMA.Brand, SCHEMA.Offer, SCHEMA.AggregateRating):
        g.add((c, RDF.type, OWL.Class))
        g.add((c, RDFS.subClassOf, ROOT))

    names = {c["name"] for c in categories}
    top: list[URIRef] = []
    for c in sorted(categories, key=lambda c: c["name"]):
        iri = class_iri(c["name"])
        g.add((iri, RDF.type, OWL.Class))
        g.add((iri, RDFS.label, Literal(c["name"], lang="en")))
        parent = c.get("parent")
        if parent and parent in names:
            g.add((iri, RDFS.subClassOf, class_iri(parent)))
        else:
            g.add((iri, RDFS.subClassOf, SCHEMA.Product))
            top.append(iri)
    # sibling top-level categories share no instances
    for i, a in enumerate(top):
        for b in top[i + 1:]:
            g.add((a, OWL.disjointWith, b))

    for prop, kind, domain, rng in PROPERTIES:
        g.add((prop, RDF.type, OWL.DatatypeProperty if kind == "datatype" else OWL.ObjectProperty))
        g.add((prop, RDFS.domain, domain))
        g.add((prop, RDFS.range, rng))
    for a, b in INVERSES:
        g.add((a, OWL.inverseOf, b))

    for cls, prop, kind, n in RESTRICTIONS:
        g.add((cls, RDFS.subClassOf, _restriction(g, prop, kind, n)))
    for d in DEFINED_CLASSES:
        _defined_class(g, d)
    return g
