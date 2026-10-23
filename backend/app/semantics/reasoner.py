"""A forward-chaining reasoner for the catalogue ontology (the Logic layer).

It applies a small, named subset of the OWL 2 RL / RDFS rule tables until nothing
new follows, and records *why* each new triple holds: the rule and the exact
premise triples. That record is what proof.py turns into an explanation.

Rules applied (ids follow the OWL 2 RL profile where one exists):

  scm-sco   subClassOf is transitive
  cax-sco   an instance of a class is an instance of its superclasses
  prp-dom   rdfs:domain types the subject of a property assertion
  prp-rng   rdfs:range types the object of a property assertion
  prp-inv   owl:inverseOf yields the reverse assertion
  cls-def   owl:equivalentClass to a property restriction (defined classes)

Checks (they report violations rather than derive triples):

  cax-dw    an instance of two owl:disjointWith classes
  cls-card  owl:cardinality / owl:maxCardinality restrictions
  dt-range  a literal whose datatype is not the property's declared range
  dt-bound  a number outside the declared bounds (price >= 0, rating 0..5)
  cls-decl  an instance of a catalogue class the ontology never declared

Not covered, on purpose: open-world satisfiability, property chains, nominals,
negation. Those need a tableau reasoner; none of them is needed for a catalogue.
"""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS, XSD

from app.semantics.ontology import RANGE_BOUNDS
from app.services.rdf_service import CAT, SCHEMA

RULES = {
    "scm-sco": ("Subclass transitivity", "If A ⊑ B and B ⊑ C then A ⊑ C."),
    "cax-sco": ("Subclass instance", "If x is an A and A ⊑ B then x is a B."),
    "prp-dom": ("Property domain", "If x p y and p has domain D then x is a D."),
    "prp-rng": ("Property range", "If x p y and p has range R then y is an R."),
    "prp-inv": ("Inverse property", "If x p y and q is the inverse of p then y q x."),
    "cls-def": ("Defined class", "If x meets every condition of a defined class, x is a member of it."),
    "cax-dw": ("Disjoint classes", "No individual may belong to two disjoint classes."),
    "cls-card": ("Cardinality", "An instance must have the number of values its class restriction demands."),
    "dt-range": ("Datatype range", "A literal must have the datatype its property declares."),
    "dt-bound": ("Value bound", "A number must lie within the bounds declared for its property."),
    "cls-decl": ("Declared class", "Every catalogue class an instance uses must be declared in the ontology."),
}


@dataclass(frozen=True)
class Derivation:
    rule: str
    premises: tuple
    note: str = ""


@dataclass(frozen=True)
class Violation:
    rule: str
    subject: object
    message: str
    premises: tuple = ()


@dataclass
class Entailment:
    graph: Graph                      # ontology + data + everything derived
    ontology: Graph
    asserted: Graph                   # the data as supplied (not the ontology)
    derived: dict = field(default_factory=dict)   # triple -> Derivation
    violations: list = field(default_factory=list)
    tbox: frozenset = frozenset()    # triples derived from the ontology alone

    def about_data(self) -> dict:
        """Derivations that involve the supplied data (not ontology-only closure)."""
        return {t: d for t, d in self.derived.items() if t not in self.tbox}

    def is_derived(self, triple) -> bool:
        return triple in self.derived

    def counts(self) -> dict:
        out: dict = {}
        for d in self.derived.values():
            out[d.rule] = out.get(d.rule, 0) + 1
        return out


def _is_node(x) -> bool:
    return isinstance(x, (URIRef, BNode))


def _decimal(lit) -> Decimal | None:
    try:
        return Decimal(str(lit))
    except (InvalidOperation, ValueError):
        return None


class Reasoner:
    def __init__(self, ontology: Graph):
        self.ontology = ontology
        self.derived: dict = {}
        self._tbox = Graph()
        for t in ontology:
            self._tbox.add(t)
        self._classes = {s for s in ontology.subjects(RDF.type, OWL.Class) if isinstance(s, URIRef)}
        self._close_subclasses()

        self.domain = self._multi(RDFS.domain)
        self.range = {p: {c for c in cs if c in self._classes} for p, cs in self._multi(RDFS.range).items()}
        self.inverse: dict = {}
        for a, b in ontology.subject_objects(OWL.inverseOf):
            self.inverse.setdefault(a, set()).add((b, (a, OWL.inverseOf, b)))
            self.inverse.setdefault(b, set()).add((a, (a, OWL.inverseOf, b)))
        self.disjoint = {
            frozenset((a, b)) for a, b in ontology.subject_objects(OWL.disjointWith)
        }
        self.restrictions = self._parse_restrictions()
        self.defined = self._parse_defined()
        self.datatype_range = {
            p: r for p, rs in self._multi(RDFS.range).items() for r in rs
            if str(r).startswith(str(XSD)) or r == RDF.langString
        }

    # ---------- T-Box ----------

    def _multi(self, pred) -> dict:
        out: dict = {}
        for s, o in self.ontology.subject_objects(pred):
            out.setdefault(s, set()).add(o)
        return out

    def _close_subclasses(self) -> None:
        """scm-sco to a fixpoint, recording the premises of each new pair."""
        t = self._tbox
        changed = True
        while changed:
            changed = False
            pairs = [(a, b) for a, b in t.subject_objects(RDFS.subClassOf) if isinstance(b, URIRef)]
            for a, b in pairs:
                for c in list(t.objects(b, RDFS.subClassOf)):
                    if not isinstance(c, URIRef) or c == a:
                        continue
                    new = (a, RDFS.subClassOf, c)
                    if new not in t:
                        t.add(new)
                        self.derived[new] = Derivation("scm-sco", ((a, RDFS.subClassOf, b), (b, RDFS.subClassOf, c)))
                        changed = True
        self.supers: dict = {}
        for a, b in t.subject_objects(RDFS.subClassOf):
            if isinstance(b, URIRef):
                self.supers.setdefault(a, set()).add(b)

    def _parse_restrictions(self) -> list:
        out = []
        for cls, r in self.ontology.subject_objects(RDFS.subClassOf):
            if not isinstance(r, BNode) or (r, RDF.type, OWL.Restriction) not in self.ontology:
                continue
            prop = self.ontology.value(r, OWL.onProperty)
            for kind in (OWL.cardinality, OWL.maxCardinality, OWL.minCardinality):
                n = self.ontology.value(r, kind)
                if n is not None:
                    out.append((cls, prop, str(kind).rsplit("#", 1)[1], int(n), (cls, RDFS.subClassOf, r)))
        return out

    def _parse_defined(self) -> list:
        """Read `C equivalentClass (Product ⊓ ∃p1.∃p2.<test>)` back out of the graph."""
        g = self.ontology
        out = []
        for cls, inter in g.subject_objects(OWL.equivalentClass):
            lst = g.value(inter, OWL.intersectionOf)
            if lst is None:
                continue
            path, test = [], None
            for member in Collection(g, lst):
                if isinstance(member, URIRef):
                    continue
                node = member
                while node is not None:
                    path.append(g.value(node, OWL.onProperty))
                    if (node, OWL.hasValue, None) in g:
                        test = ("value", g.value(node, OWL.hasValue))
                        break
                    inner = g.value(node, OWL.someValuesFrom)
                    if inner is not None and (inner, OWL.onDatatype, None) in g:
                        facet = Collection(g, g.value(inner, OWL.withRestrictions))[0]
                        test = ("min", _decimal(g.value(facet, XSD.minInclusive)))
                        break
                    node = inner
            if path and test:
                out.append((cls, tuple(path), test, (cls, OWL.equivalentClass, inter)))
        return out

    # ---------- A-Box ----------

    def entail(self, data: Graph) -> Entailment:
        g = Graph()
        for t in self._tbox:
            g.add(t)
        for t in data:
            g.add(t)
        for prefix, ns in data.namespaces():
            g.bind(prefix, ns, override=True, replace=True)
        for prefix, ns in self.ontology.namespaces():
            g.bind(prefix, ns, override=True, replace=True)
        derived = dict(self.derived)

        def add(triple, rule, premises, note=""):
            if triple in g:
                return False
            g.add(triple)
            derived[triple] = Derivation(rule, tuple(premises), note)
            return True

        changed = True
        while changed:
            changed = False
            for s, p, o in list(g):
                for q, axiom in self.inverse.get(p, ()):
                    if _is_node(o):
                        changed |= add((o, q, s), "prp-inv", [(s, p, o), axiom])
                for d in self.domain.get(p, ()):
                    if d in self._classes:
                        changed |= add((s, RDF.type, d), "prp-dom", [(s, p, o), (p, RDFS.domain, d)])
                if _is_node(o):
                    for r in self.range.get(p, ()):
                        changed |= add((o, RDF.type, r), "prp-rng", [(s, p, o), (p, RDFS.range, r)])
                if p == RDF.type:
                    for c in self.supers.get(o, ()):
                        changed |= add((s, RDF.type, c), "cax-sco", [(s, p, o), (o, RDFS.subClassOf, c)])
            changed |= self._apply_defined(g, add)

        ent = Entailment(graph=g, ontology=self.ontology, asserted=data, derived=derived,
                         tbox=frozenset(self.derived))
        ent.violations = self._check(ent)
        return ent

    def _apply_defined(self, g: Graph, add) -> bool:
        changed = False
        for cls, path, (kind, arg), axiom in self.defined:
            for s in list(g.subjects(RDF.type, SCHEMA.Product)):
                for chain, value in self._walk(g, s, path):
                    ok = (value == arg) if kind == "value" else (
                        isinstance(value, Literal) and (v := _decimal(value)) is not None and v >= arg)
                    if ok:
                        note = f"{value} ≥ {arg}" if kind == "min" else f"value is {_q(g, value)}"
                        changed |= add((s, RDF.type, cls), "cls-def", [*chain, axiom], note)
        return changed

    @staticmethod
    def _walk(g: Graph, node, path):
        """Yield (premise triples, final value) for every way to follow `path`."""
        frontier = [([], node)]
        for prop in path:
            frontier = [(chain + [(n, prop, o)], o) for chain, n in frontier for o in g.objects(n, prop)]
        return frontier

    # ---------- checks ----------

    def _check(self, ent: Entailment) -> list:
        g, data = ent.graph, ent.asserted
        found: list = []

        # cax-dw
        for s in set(data.subjects(RDF.type, None)):
            types = [t for t in g.objects(s, RDF.type) if isinstance(t, URIRef)]
            for i, a in enumerate(types):
                for b in types[i + 1:]:
                    if frozenset((a, b)) in self.disjoint:
                        ax = (a, OWL.disjointWith, b) if (a, OWL.disjointWith, b) in g else (b, OWL.disjointWith, a)
                        found.append(Violation(
                            "cax-dw", s, f"is both {_q(g, a)} and {_q(g, b)}, which are disjoint",
                            ((s, RDF.type, a), (s, RDF.type, b), ax)))

        # cls-decl
        for s, t in data.subject_objects(RDF.type):
            if isinstance(t, URIRef) and str(t).startswith(str(CAT)) and t not in self._classes:
                found.append(Violation("cls-decl", s, f"is typed {_q(g, t)}, which the ontology does not declare",
                                       ((s, RDF.type, t),)))

        # cls-card
        in_data = set(data.all_nodes())
        for cls, prop, kind, n, axiom in self.restrictions:
            for s in set(g.subjects(RDF.type, cls)):
                if s not in in_data:
                    continue
                count = len(set(g.objects(s, prop)))
                bad = (kind == "cardinality" and count != n) or (kind == "maxCardinality" and count > n) \
                    or (kind == "minCardinality" and count < n)
                if bad:
                    found.append(Violation(
                        "cls-card", s,
                        f"has {count} value(s) for {_q(g, prop)}; {_q(g, cls)} requires {kind} {n}",
                        ((s, RDF.type, cls), axiom)))

        # dt-range, dt-bound
        bounds = {p: (lo, hi) for p, lo, hi in RANGE_BOUNDS}
        for s, p, o in data:
            if not isinstance(o, Literal):
                continue
            want = self.datatype_range.get(p)
            if want is not None:
                got = RDF.langString if o.language else o.datatype
                if got != want:
                    found.append(Violation(
                        "dt-range", s, f"{_q(g, p)} value {o.n3()} should be {_q(g, want)}",
                        ((s, p, o), (p, RDFS.range, want))))
            if p in bounds:
                v = _decimal(o)
                lo, hi = bounds[p]
                if v is not None and ((lo is not None and v < lo) or (hi is not None and v > hi)):
                    found.append(Violation(
                        "dt-bound", s, f"{_q(g, p)} value {v} is outside [{lo}, {hi if hi is not None else '∞'}]",
                        ((s, p, o),)))
        return found


def _q(g: Graph, term) -> str:
    return term.n3(g.namespace_manager) if hasattr(term, "n3") else str(term)
