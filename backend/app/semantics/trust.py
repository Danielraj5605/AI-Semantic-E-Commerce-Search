"""Trust layer: provenance, confidence you can defend, and tamper evidence.

Three separate questions, three mechanisms:

1. Where did this come from?   A PROV-O graph per product: the entity, the mapping
   activity that produced it, the agent, and a reified statement for every
   *inferred* triple naming the rule that derived it.
2. How much should I believe it?   Asserted rows and deductive inferences are
   certain relative to the catalogue (a sound rule cannot add doubt). The only
   probabilistic claim the system makes is "this product matches your query", and
   its confidence is the *measured* precision at that similarity score, read from
   eval/calibration.json. It is not a guess about what a score ought to mean.
3. Has it been altered?   The asserted graph is canonicalised (blank nodes
   relabelled deterministically), hashed with SHA-256, and signed with HMAC-SHA256.
   Anyone holding the key can verify a copy of the graph; changing one triple
   changes the digest.
"""

import hashlib
import hmac
import json
from decimal import Decimal
from pathlib import Path

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.compare import to_canonical_graph
from rdflib.namespace import DCTERMS, PROV, RDF, XSD

from app.config import get_settings
from app.semantics.reasoner import RULES, Entailment
from app.services.rdf_service import CAT, _decimal, _ex

CALIBRATION_PATH = Path(__file__).resolve().parent.parent.parent / "eval" / "calibration.json"
DEV_KEY = "catalogue-graph-development-key"


# ---------- 1. provenance ----------

def provenance_graph(product: dict, ent: Entailment, subject: URIRef) -> Graph:
    ex = _ex()
    g = Graph()
    for prefix, ns in (("prov", PROV), ("cat", CAT), ("ex", ex), ("xsd", XSD), ("dcterms", DCTERMS)):
        g.bind(prefix, ns, override=True, replace=True)
    pid = product["product_id"]

    table = URIRef(f"{ex}table/products")
    activity = URIRef(f"{ex}activity/lift/{pid}")
    agent = URIRef(f"{ex}agent/direct-mapping")
    reasoner = URIRef(f"{ex}agent/rl-reasoner")
    entailment = URIRef(f"{ex}activity/entail/{pid}")

    g.add((table, RDF.type, PROV.Entity))
    g.add((agent, RDF.type, PROV.SoftwareAgent))
    g.add((reasoner, RDF.type, PROV.SoftwareAgent))
    g.add((subject, RDF.type, PROV.Entity))
    g.add((subject, PROV.wasDerivedFrom, table))
    g.add((subject, PROV.wasGeneratedBy, activity))
    g.add((activity, RDF.type, PROV.Activity))
    g.add((activity, PROV.used, table))
    g.add((activity, PROV.wasAssociatedWith, agent))
    if product.get("created_at"):
        g.add((subject, PROV.generatedAtTime, Literal(product["created_at"], datatype=XSD.dateTime)))

    g.add((entailment, RDF.type, PROV.Activity))
    g.add((entailment, PROV.used, subject))
    g.add((entailment, PROV.wasAssociatedWith, reasoner))

    # one reified statement per inference about this product
    for n, (triple, d) in enumerate(sorted(ent.about_data().items(), key=lambda kv: str(kv[0]))):
        s, p, o = triple
        stmt = URIRef(f"{ex}inference/{pid}/{n}")
        g.add((stmt, RDF.type, RDF.Statement))
        g.add((stmt, RDF.type, PROV.Entity))
        g.add((stmt, RDF.subject, s))
        g.add((stmt, RDF.predicate, p))
        g.add((stmt, RDF.object, o))
        g.add((stmt, PROV.wasGeneratedBy, entailment))
        g.add((stmt, CAT.derivedByRule, URIRef(f"{CAT}rule/{d.rule}")))
        g.add((stmt, CAT.confidence, _decimal(Decimal("1.0"))))
    for rule, (name, text) in RULES.items():
        iri = URIRef(f"{CAT}rule/{rule}")
        g.add((iri, RDF.type, PROV.Plan))
        g.add((iri, DCTERMS.title, Literal(name, lang="en")))
        g.add((iri, DCTERMS.description, Literal(text, lang="en")))
    return g


# ---------- 2. calibrated confidence ----------

def load_calibration() -> dict | None:
    try:
        return json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def calibrated_confidence(score: float | None, calibration: dict | None = None) -> dict:
    """Measured precision of results at this similarity score, with its sample size."""
    cal = calibration if calibration is not None else load_calibration()
    if score is None or not cal:
        return {"confidence": None, "n": 0, "basis": "no calibration data"}
    for b in cal["bins"]:
        if b["lo"] <= score < b["hi"] or (b["hi"] >= 1.0 and score >= b["lo"]):
            return {"confidence": b["precision"], "n": b["n"], "lo": b["lo"], "hi": b["hi"],
                    "basis": f"{b['relevant']} of {b['n']} labelled results with similarity "
                             f"{b['lo']:.2f}–{min(b['hi'], 1.0):.2f} were relevant"}
    return {"confidence": 0.0, "n": 0, "basis": "below the lowest calibrated bin"}


def pool_adjacent_violators(points: list[tuple[int, int]]) -> list[float]:
    """Monotone (non-decreasing) precision: a higher score never claims lower confidence.

    points are (relevant, total) per bin from low score to high.
    """
    blocks = [[r, n, 1] for r, n in points]  # relevant, total, bins merged
    i = 0
    while i < len(blocks) - 1:
        a, b = blocks[i], blocks[i + 1]
        if b[1] and a[1] and a[0] / a[1] > b[0] / b[1]:
            blocks[i:i + 2] = [[a[0] + b[0], a[1] + b[1], a[2] + b[2]]]
            i = max(i - 1, 0)
        else:
            i += 1
    out: list[float] = []
    for r, n, width in blocks:
        out += [r / n if n else 0.0] * width
    return out


# ---------- 3. integrity ----------

def signing_key() -> tuple[bytes, str]:
    s = get_settings()
    if s.trust_key:
        return s.trust_key.encode(), "TRUST_KEY"
    if s.admin_token:
        return s.admin_token.encode(), "ADMIN_TOKEN"
    return DEV_KEY.encode(), "development-default"


def canonical_ntriples(graph: Graph) -> str:
    """Deterministic serialisation: blank nodes relabelled, lines sorted."""
    canon = to_canonical_graph(graph)
    return "\n".join(sorted(line for line in canon.serialize(format="nt").splitlines() if line.strip()))


def digest(graph: Graph) -> str:
    return hashlib.sha256(canonical_ntriples(graph).encode("utf-8")).hexdigest()


def sign(digest_hex: str) -> str:
    key, _ = signing_key()
    return hmac.new(key, digest_hex.encode("ascii"), hashlib.sha256).hexdigest()


def verify(graph: Graph, signature: str) -> tuple[bool, str]:
    d = digest(graph)
    return hmac.compare_digest(sign(d), signature or ""), d
