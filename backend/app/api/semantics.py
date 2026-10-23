"""Routes for the upper Semantic Web layers: ontology, logic, proof and trust."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel
from rdflib import BNode, Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.models import Category, Product
from app.semantics import ontology as onto
from app.semantics import proof, trust
from app.semantics.reasoner import RULES, Reasoner
from app.services import rdf_service
from app.services.search_service import _format_result, get_product_row

router = APIRouter(prefix="/api", tags=["semantics"])

_reasoners: dict = {}


async def load_reasoner(db: AsyncSession) -> Reasoner:
    """One reasoner per class hierarchy; the T-Box is closed once and reused."""
    rows = (await db.execute(select(Category))).scalars().all()
    by_id = {c.category_id: c.name for c in rows}
    cats = [{"name": c.name, "parent": by_id.get(c.parent_category_id)} for c in rows]
    key = tuple(sorted((c["name"], c["parent"] or "") for c in cats))
    if key not in _reasoners:
        _reasoners.clear()
        _reasoners[key] = Reasoner(onto.build_ontology(cats))
    return _reasoners[key]


def _wants(accept: Optional[str], fmt: Optional[str]) -> Optional[str]:
    try:
        return rdf_service.negotiate(accept, fmt)
    except ValueError as err:
        raise HTTPException(status_code=406, detail=str(err))


def _rdf(graph: Graph, media_type: str, **headers) -> Response:
    return Response(content=rdf_service.serialise(graph, media_type), media_type=media_type,
                    headers={"Vary": "Accept", **headers})


async def _product(db: AsyncSession, product_id: UUID) -> dict:
    p = await get_product_row(db, product_id)
    if p is None:
        raise HTTPException(status_code=404, detail="unknown product")
    return p


# ---------- OWL ----------

def _qname(g: Graph, term) -> str:
    return term.n3(g.namespace_manager)


def ontology_summary(r: Reasoner) -> dict:
    g = r.ontology
    classes = []
    for c in sorted(r._classes, key=str):
        parents = [p for p in g.objects(c, RDFS.subClassOf) if isinstance(p, URIRef)]
        classes.append({
            "iri": str(c), "qname": _qname(g, c),
            "label": str(g.value(c, RDFS.label) or ""),
            "parents": sorted(_qname(g, p) for p in parents),
            "disjoint_with": sorted(_qname(g, o) for o in set(g.objects(c, OWL.disjointWith)) | set(g.subjects(OWL.disjointWith, c))),
            "defined": any(c == d[0] for d in r.defined),
        })
    props = []
    for p in sorted(set(g.subjects(RDF.type, OWL.ObjectProperty)) | set(g.subjects(RDF.type, OWL.DatatypeProperty)), key=str):
        props.append({
            "qname": _qname(g, p),
            "kind": "object" if (p, RDF.type, OWL.ObjectProperty) in g else "datatype",
            "domain": [_qname(g, d) for d in g.objects(p, RDFS.domain)],
            "range": [_qname(g, d) for d in g.objects(p, RDFS.range)],
            "inverse_of": [_qname(g, i) for i in g.objects(p, OWL.inverseOf)] + [_qname(g, i) for i in g.subjects(OWL.inverseOf, p)],
        })
    return {
        "iri": str(onto.ONTOLOGY_IRI),
        "triples": len(g),
        "classes": classes,
        "properties": props,
        "restrictions": [
            {"class": _qname(g, c), "property": _qname(g, p), "kind": k, "value": n}
            for c, p, k, n, _ in r.restrictions
        ],
        "defined_classes": [
            {"class": _qname(g, c), "path": [_qname(g, p) for p in path],
             "test": {"kind": t[0], "value": str(t[1]) if t[0] == "min" else _qname(g, t[1])},
             "comment": str(g.value(c, RDFS.comment) or "")}
            for c, path, t, _ in r.defined
        ],
    }


@router.get("/ontology")
async def get_ontology(
    format: Optional[str] = Query(None, description="ttl | rdf | jsonld | json — overrides Accept"),
    accept: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """The OWL ontology the reasoner uses. JSON summary by default; RDF by negotiation."""
    media_type = _wants(accept, format)
    r = await load_reasoner(db)
    if media_type is None:
        return ontology_summary(r)
    return _rdf(r.ontology, media_type)


@router.get("/ontology/validate")
async def validate_catalogue(db: AsyncSession = Depends(get_db)):
    """Check every product against the ontology: does the catalogue conform?"""
    r = await load_reasoner(db)
    rows = (await db.execute(
        select(Product, Category.name).outerjoin(Category, Product.category_id == Category.category_id)
    )).all()
    data = Graph()
    for product, cat_name in rows:
        for t in rdf_service.product_graph(_format_result(product, cat_name, 0)["product"]):
            data.add(t)
    ent = r.entail(data)
    inferred_types = sum(1 for t in ent.about_data() if t[1] == RDF.type)
    return {
        "conforms": not ent.violations,
        "products_checked": len(rows),
        "asserted_triples": len(data),
        "inferred_triples": len(ent.about_data()),
        "inferred_types": inferred_types,
        "by_rule": ent.counts(),
        "violations": [
            {"rule": v.rule, "subject": proof.fmt(ent, v.subject), "message": v.message}
            for v in ent.violations
        ],
    }


# ---------- Logic ----------

@router.get("/logic/rules")
async def list_rules():
    return [{"id": k, "name": n, "text": t} for k, (n, t) in RULES.items()]


@router.get("/product/{product_id}/inferences")
async def inferences(
    product_id: UUID,
    format: Optional[str] = Query(None),
    accept: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """What follows from this product's row plus the ontology (RDF = asserted + inferred)."""
    media_type = _wants(accept, format)
    product = await _product(db, product_id)
    r = await load_reasoner(db)
    data = rdf_service.product_graph(product)
    ent = r.entail(data)
    subject = rdf_service.product_uri(product_id)

    if media_type is not None:
        view = Graph()
        for prefix, ns in ent.graph.namespaces():
            view.bind(prefix, ns, override=False)
        for t in ent.graph:
            if t in data or t in ent.about_data():
                view.add(t)
        return _rdf(view, media_type)

    inferred = [
        {"triple": proof.statement(ent, t), "rule": d.rule, "rule_name": RULES[d.rule][0], "note": d.note}
        for t, d in ent.about_data().items()
    ]
    inferred.sort(key=lambda x: (x["rule"], x["triple"]))
    return {
        "product": str(subject),
        "asserted": len(data),
        "inferred": inferred,
        "consistent": not ent.violations,
        "violations": [{"rule": v.rule, "message": v.message} for v in ent.violations],
    }


# ---------- Proof ----------

@router.get("/product/{product_id}/proof")
async def product_proof(product_id: UUID, db: AsyncSession = Depends(get_db)):
    """A proof tree for every fact inferred about this product."""
    product = await _product(db, product_id)
    r = await load_reasoner(db)
    ent = r.entail(rdf_service.product_graph(product))
    subject = rdf_service.product_uri(product_id)
    items = proof.proofs_for(ent)
    for x in items:
        x["text"] = proof.render(x["proof"])
        x["depth"] = proof.depth(x["proof"])
        x["grounded_in"] = len(proof.leaves(x["proof"]))
    return {"product": str(subject), "proofs": items}


# ---------- Trust ----------

@router.get("/trust/calibration")
async def calibration():
    """Measured precision of search results by similarity score (see eval/calibrate.py)."""
    cal = trust.load_calibration()
    if cal is None:
        raise HTTPException(status_code=404, detail="no calibration yet: run python -m eval.calibrate")
    return cal


@router.get("/product/{product_id}/provenance")
async def provenance(
    product_id: UUID,
    format: Optional[str] = Query(None),
    accept: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """PROV-O provenance, plus a signed digest of the product's asserted graph."""
    media_type = _wants(accept, format)
    product = await _product(db, product_id)
    r = await load_reasoner(db)
    data = rdf_service.product_graph(product)
    ent = r.entail(data)
    subject = rdf_service.product_uri(product_id)
    prov = trust.provenance_graph(product, ent, subject)
    d = trust.digest(data)
    signature = trust.sign(d)
    _, key_source = trust.signing_key()

    if media_type is not None:
        return _rdf(prov, media_type, **{"X-Content-Digest": d, "X-Content-Signature": signature})
    return {
        "product": str(subject),
        "digest": d, "digest_algorithm": "sha256 over canonical N-Triples",
        "signature": signature, "signature_algorithm": "HMAC-SHA256", "key_source": key_source,
        "graph_turtle": data.serialize(format="turtle"),
        "provenance_turtle": prov.serialize(format="turtle"),
        "inferences_recorded": len(ent.about_data()),
    }


class VerifyRequest(BaseModel):
    turtle: str
    signature: str
    product_id: Optional[UUID] = None


@router.post("/verify")
async def verify(body: VerifyRequest, db: AsyncSession = Depends(get_db)):
    """Is this graph exactly what was signed? Optionally: is it still what the catalogue says?"""
    graph = Graph()
    try:
        graph.parse(data=body.turtle, format="turtle")
    except Exception as err:
        raise HTTPException(status_code=422, detail=f"not valid Turtle: {str(err)[:120]}")
    ok, d = trust.verify(graph, body.signature)
    out = {"signature_valid": ok, "digest": d, "triples": len(graph)}
    if body.product_id is not None:
        current = await _product(db, body.product_id)
        out["matches_catalogue"] = d == trust.digest(rdf_service.product_graph(current))
    return out
