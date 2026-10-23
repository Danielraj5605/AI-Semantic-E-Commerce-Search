"""Proof layer: turn the reasoner's derivation records into explanations.

A proof for a triple is a tree. A leaf is something the system was *told*, either
by the catalogue (a database row) or by the ontology (an axiom). An inner node is
a rule application with the premises it used. Anything the reasoner derived can
be traced to leaves, and anything it did not derive has no proof, which is the
point: the answer is checkable, not just asserted.
"""

from rdflib import BNode, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from app.semantics.reasoner import RULES, Entailment

MAX_DEPTH = 12


def fmt(ent: Entailment, term) -> str:
    nm = ent.graph.namespace_manager
    if isinstance(term, BNode):
        for _, p in ent.graph.subject_predicates(term):
            return "_:" + str(p).rsplit("/", 1)[-1].rsplit("#", 1)[-1]
        return "_:b"
    if isinstance(term, Literal):
        return term.n3(nm)
    if isinstance(term, URIRef):
        short = term.n3(nm)
        if not short.startswith("<"):
            return short
        # product/brand URIs have a "/" in the local part, so they are not QNames
        for prefix, ns in nm.namespaces():
            if str(term).startswith(str(ns)) and prefix:
                return f"{prefix}:{str(term)[len(str(ns)):]}"
        return short
    return str(term)


def statement(ent: Entailment, triple) -> str:
    s, p, o = triple
    obj = "(class expression)" if isinstance(o, BNode) and p in (RDFS.subClassOf, OWL.equivalentClass) else fmt(ent, o)
    return f"{fmt(ent, s)} {fmt(ent, p)} {obj}"


def _leaf(ent: Entailment, triple) -> dict:
    if triple in ent.asserted:
        kind, source = "asserted", "catalogue row (ex:table/products)"
    elif triple in ent.ontology:
        kind, source = "axiom", "catalogue ontology"
    else:
        kind, source = "unknown", "not derivable"
    return {"statement": statement(ent, triple), "kind": kind, "source": source}


def explain(ent: Entailment, triple, _depth: int = 0, _seen: tuple = ()) -> dict:
    """The proof tree for one triple (a leaf if it was asserted, not derived)."""
    d = ent.derived.get(triple)
    if d is None or _depth >= MAX_DEPTH or triple in _seen:
        return _leaf(ent, triple)
    name, general = RULES[d.rule]
    return {
        "statement": statement(ent, triple),
        "kind": "derived",
        "rule": d.rule,
        "rule_name": name,
        "rule_text": general,
        "note": d.note,
        "premises": [explain(ent, t, _depth + 1, _seen + (triple,)) for t in d.premises],
    }


def render(node: dict, indent: int = 0) -> str:
    pad = "  " * indent
    if node["kind"] != "derived":
        return f"{pad}{node['statement']}   [{node['kind']}: {node['source']}]"
    head = f"{pad}{node['statement']}   [{node['rule']}: {node['rule_name']}"
    head += f"; {node['note']}]" if node["note"] else "]"
    return "\n".join([head, *(render(p, indent + 1) for p in node["premises"])])


def leaves(node: dict) -> list:
    if node["kind"] != "derived":
        return [node]
    return [leaf for p in node["premises"] for leaf in leaves(p)]


def depth(node: dict) -> int:
    return 1 + max((depth(p) for p in node.get("premises", [])), default=0)


def proofs_for(ent: Entailment) -> list[dict]:
    """A proof for every fact derived from the supplied data (ontology-only closure excluded)."""
    out = [
        {"conclusion": statement(ent, t), "rule": d.rule, "proof": explain(ent, t)}
        for t, d in ent.about_data().items()
    ]
    out.sort(key=lambda x: (x["rule"], x["conclusion"]))
    return out


def is_type_fact(triple) -> bool:
    return triple[1] == RDF.type
