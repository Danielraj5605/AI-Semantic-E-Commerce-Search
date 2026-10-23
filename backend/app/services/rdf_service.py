"""Server-side RDF view of a product row.

The same direct-mapping rules as frontend/src/rdf.js, built on rdflib so the
output can be served by content negotiation (Linked Data) and used to
cross-check the hand-written serialisers in the browser.

Like the frontend, the graph is derived from the row on every request; nothing
is stored, so it cannot drift from the relational source.
"""

import re
from decimal import Decimal

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, PROV, RDF, RDFS, XSD

from app.config import get_settings

SCHEMA = Namespace("http://schema.org/")
CAT = Namespace("http://example.org/ontology/catalog#")

# (media type, rdflib format, file extension) — first entry is the default for "*/*"
FORMATS = {
    "text/turtle": ("turtle", "ttl"),
    "application/rdf+xml": ("xml", "rdf"),
    "application/ld+json": ("json-ld", "jsonld"),
}
EXTENSIONS = {ext: mt for mt, (_, ext) in FORMATS.items()} | {"xml": "application/rdf+xml", "json": None}


def local_name(text: str | None) -> str:
    """PascalCase QName-safe local name; mirrors localName() in rdf.js."""
    if not text:
        return "Thing"
    cleaned = re.sub(r"[^A-Za-z0-9\s-]", " ", re.sub(r"['’]", "", str(text)))
    parts = [p for p in re.split(r"[\s-]+", cleaned) if p]
    return "".join(p[:1].upper() + p[1:].lower() for p in parts) or "Thing"


def slug(text: str | None) -> str:
    """Lower-case hyphenated slug; mirrors slug() in rdf.js."""
    return re.sub(r"(^-|-$)", "", re.sub(r"[^a-z0-9]+", "-", str(text or "").lower())) or "unnamed"


def _ex() -> Namespace:
    base = get_settings().base_uri
    return Namespace(base if base.endswith(("/", "#")) else base + "/")


def product_uri(product_id) -> URIRef:
    return URIRef(f"{_ex()}product/{product_id}")


def _decimal(value) -> Literal:
    """xsd:decimal with a pinned lexical form.

    rdflib would otherwise normalise 5 to "5.0" in Turtle but write "5" in
    RDF/XML and JSON-LD, so the three syntaxes would disagree on the same graph.
    """
    return Literal(str(value), datatype=XSD.decimal, normalize=False)


def product_graph(product: dict) -> Graph:
    """Lift one product dict (as returned by get_product_row) into RDF."""
    ex = _ex()
    g = Graph()
    for prefix, ns in (
        ("schema", SCHEMA), ("dcterms", DCTERMS), ("prov", PROV), ("cat", CAT),
        ("owl", OWL), ("rdfs", RDFS), ("xsd", XSD), ("ex", ex),
    ):
        g.bind(prefix, ns, override=True, replace=True)

    s = product_uri(product["product_id"])
    g.add((s, RDF.type, SCHEMA.Product))

    if product.get("category_name"):
        cls = CAT[local_name(product["category_name"])]
        g.add((s, RDF.type, cls))
        g.add((s, SCHEMA.category, cls))
    if product.get("name"):
        g.add((s, SCHEMA.name, Literal(product["name"], lang="en")))
    if product.get("description"):
        g.add((s, SCHEMA.description, Literal(product["description"], lang="en")))

    if product.get("brand"):
        brand = URIRef(f"{ex}brand/{slug(product['brand'])}")
        g.add((s, SCHEMA.brand, brand))
        g.add((brand, RDF.type, SCHEMA.Brand))
        g.add((brand, SCHEMA.name, Literal(product["brand"])))

    if product.get("image_url"):
        g.add((s, SCHEMA.image, URIRef(product["image_url"])))

    if product.get("price") is not None:
        offer = BNode()
        g.add((s, SCHEMA.offers, offer))
        g.add((offer, RDF.type, SCHEMA.Offer))
        g.add((offer, SCHEMA.price, _decimal(Decimal(str(product["price"])).quantize(Decimal("0.01")))))
        g.add((offer, SCHEMA.priceCurrency, Literal("USD")))
        in_stock = (product.get("stock_quantity") or 0) > 0
        g.add((offer, SCHEMA.availability, SCHEMA.InStock if in_stock else SCHEMA.OutOfStock))

    if product.get("rating_avg"):
        rating = BNode()
        g.add((s, SCHEMA.aggregateRating, rating))
        g.add((rating, RDF.type, SCHEMA.AggregateRating))
        g.add((rating, SCHEMA.ratingValue, _decimal(Decimal(str(product["rating_avg"])).quantize(Decimal("0.1")))))
        g.add((rating, SCHEMA.bestRating, _decimal("5.0")))

    if product.get("created_at"):
        g.add((s, DCTERMS.created, Literal(product["created_at"], datatype=XSD.dateTime)))

    g.add((s, PROV.wasDerivedFrom, URIRef(f"{ex}table/products")))
    return g


def negotiate(accept: str | None, fmt: str | None = None) -> str | None:
    """Pick a media type from `?format=` or the Accept header.

    Returns an RDF media type, or None for plain JSON (the default for browsers
    and API clients that do not ask for RDF).
    """
    if fmt:
        wanted = EXTENSIONS.get(fmt.lower().lstrip("."))
        if fmt.lower() in {"json"}:
            return None
        if wanted is None:
            raise ValueError(f"unknown format: {fmt}")
        return wanted

    ranked: list[tuple[float, int, str]] = []
    for i, part in enumerate((accept or "").split(",")):
        pieces = [p.strip() for p in part.split(";")]
        mt, q = pieces[0].lower(), 1.0
        for extra in pieces[1:]:
            if extra.startswith("q="):
                try:
                    q = float(extra[2:])
                except ValueError:
                    q = 0.0
        if q > 0:
            ranked.append((-q, i, mt))
    for _, _, mt in sorted(ranked):
        if mt in FORMATS:
            return mt
        if mt in ("application/json", "*/*", "text/html"):
            return None
    return None


def serialise(graph: Graph, media_type: str) -> str:
    return graph.serialize(format=FORMATS[media_type][0])
