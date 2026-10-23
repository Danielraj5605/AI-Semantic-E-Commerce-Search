/**
 * concepts.js — the didactic content of the interface.
 *
 * The application is a coursework artefact for 21CSE452T (Semantic Web), so the
 * UI is expected to *show its working*: which layer of the Semantic Web stack a
 * given screen element belongs to, and which unit of the syllabus it answers to.
 * Keeping that content here rather than inline in JSX keeps App.jsx about
 * behaviour and this file about the subject matter.
 */

/* ============================================================
   THE LAYER CAKE  (Unit 1)
   Bottom-to-top, as in Berners-Lee's stack diagram. `state` records
   how far this particular application actually climbs. Each layer states
   its scope, including where it stops short of the full standard.
   ============================================================ */

export const LAYER_CAKE = [
  {
    layer: "URI / Unicode",
    role: "Identity and character encoding",
    here: "Every product, brand and class gets a dereferenceable URI in the ex: and cat: namespaces.",
    state: "full",
  },
  {
    layer: "XML + Namespaces",
    role: "Syntax and vocabulary separation",
    here: "The graph serialises to RDF/XML with prefixed vocabularies; no term collides.",
    state: "full",
  },
  {
    layer: "RDF",
    role: "Statements as subject–predicate–object",
    here: "Each catalogue row is lifted into triples over schema.org and Dublin Core.",
    state: "full",
  },
  {
    layer: "RDF Schema",
    role: "Classes, properties, subsumption",
    here: "Categories become owl:Class nodes joined by rdfs:subClassOf into a taxonomy.",
    state: "full",
  },
  {
    layer: "Ontology (OWL)",
    role: "Richer axioms and constraints",
    here: "A real OWL ontology at /api/ontology: class hierarchy, disjointness, domain/range, an inverse property, cardinality restrictions, and defined classes (TopRated, Premium, InStockProduct) stated as owl:equivalentClass. OWL 2 RL style, not OWL DL.",
    state: "full",
  },
  {
    layer: "Logic",
    role: "Rules and entailment",
    here: "A forward-chaining reasoner applies six RDFS/OWL-RL rules (subclass, domain, range, inverse, defined classes) to every product, and five checks (disjointness, cardinality, datatype, bounds, declared classes) validate the whole catalogue.",
    state: "full",
  },
  {
    layer: "Proof",
    role: "Explaining why an answer holds",
    here: "Every inferred fact carries a proof tree: the rule, its premises, and down to the catalogue rows and ontology axioms it rests on. Open Reasoning on any result.",
    state: "full",
  },
  {
    layer: "Trust",
    role: "Deciding whether to believe it",
    here: "PROV-O provenance for every product and inference; match confidence measured against the labelled evaluation, not assumed; and an HMAC-signed digest of each graph that detects a single altered triple.",
    state: "full",
  },
];

/* ============================================================
   SYLLABUS MAP
   Ties each surface of the app back to a unit, so the interface can
   be read as a walkthrough of the course.
   ============================================================ */

export const UNIT_MAP = [
  {
    id: "unit-1",
    unit: "Unit 1",
    title: "The Semantic Web",
    topics: "Layer cake · RDF · properties · visualisation · annotation · searching strategies",
    surfaces: "Layer-cake panel, triple table, graph visualisation, annotation badges on results.",
  },
  {
    id: "unit-2",
    unit: "Unit 2",
    title: "Understanding Ontologies",
    topics: "Syntax · structure · semantics · pragmatics · OWL · levels of ontologies",
    surfaces: "Ontology browser in the left rail: the class tree, its axioms and QNames.",
  },
  {
    id: "unit-3",
    unit: "Unit 3",
    title: "Semantic Web Services",
    topics: "Invoking · describing · finding services · agents · distributed trust and belief",
    surfaces: "Service descriptor strip and the trust/provenance row under each result.",
  },
  {
    id: "unit-4",
    unit: "Unit 4",
    title: "Ontology Engineering",
    topics: "Reusing ontologies · ontology mapping · exposing relational databases",
    surfaces: "Mapping panel: the column-by-column rules that lift SQL rows into the graph.",
  },
  {
    id: "unit-5",
    unit: "Unit 5",
    title: "Case Studies with XML",
    topics: "XML · structuring · namespaces · addressing and querying · FOAF",
    surfaces: "Serialisation tabs (Turtle / RDF-XML / JSON-LD), prefix table, SPARQL view.",
  },
];

/* ============================================================
   SERVICE DESCRIPTION  (Unit 3 — describing and invoking services)
   A WSDL-in-miniature: what the agent called, and how.
   ============================================================ */

export function describeService(mode) {
  return mode === "semantic"
    ? {
        name: "cat:SemanticSearchService",
        operation: "GET /api/search",
        binding: "REST · application/json",
        method: "Vector nearest-neighbour over pgvector (cosine distance)",
        agent: "all-MiniLM-L6-v2 · 384-dimension sentence encoder",
      }
    : {
        name: "cat:KeywordSearchService",
        operation: "GET /api/search/keyword",
        binding: "REST · application/json",
        method: "SQL ILIKE substring match — the syntactic baseline",
        agent: "none · no encoder in the request path",
      };
}

/* ============================================================
   TRUST AND BELIEF  (Unit 3)
   Turns a raw similarity score into a stated degree of belief, with
   the reason attached. Never asserts confidence it cannot justify.
   ============================================================ */

/**
 * Thresholds calibrated against the observed cosine distribution of
 * all-MiniLM-L6-v2 over this catalogue, not chosen a priori. Sampling several
 * queries against the live index:
 *
 *   "warm winter jacket for men" -> Insulated Men's Parka          0.648
 *   "noise cancelling headphones" -> NoiseCancel Pro Headphones    0.524
 *                                 -> TrueWireless Earbuds Sport    0.332
 *                                 -> Studio Monitor Speakers       0.165
 *
 * An unambiguously correct answer lands around 0.50-0.65; a merely related one
 * around 0.32-0.50; the irrelevant tail below 0.32. MiniLM's cosine scores are
 * compressed and rarely approach 1.0, so textbook thresholds would mark correct
 * results as doubtful — which is worse than saying nothing, because the whole
 * point of the band is to be believed.
 *
 * Re-sample these if the embedding model or the catalogue changes.
 */
export const BELIEF_THRESHOLDS = { strong: 0.5, moderate: 0.32 };

export function trustBand(score, mode) {
  if (mode === "keyword") {
    return {
      label: "Asserted",
      level: "asserted",
      basis: "Literal substring match — certain, but blind to meaning.",
    };
  }
  if (score === null || score === undefined) {
    return { label: "Unscored", level: "unknown", basis: "No similarity score returned." };
  }
  if (score >= BELIEF_THRESHOLDS.strong) {
    return {
      label: "Strong belief",
      level: "strong",
      basis: `Cosine similarity ${score.toFixed(3)} — at or above the ${BELIEF_THRESHOLDS.strong} band where matches on this catalogue are reliably on-target.`,
    };
  }
  if (score >= BELIEF_THRESHOLDS.moderate) {
    return {
      label: "Moderate belief",
      level: "moderate",
      basis: `Cosine similarity ${score.toFixed(3)} — related in meaning, but not a direct answer to the query.`,
    };
  }
  return {
    label: "Weak belief",
    level: "weak",
    basis: `Cosine similarity ${score.toFixed(3)} — below ${BELIEF_THRESHOLDS.moderate}; distant in vector space, so treat as a peripheral suggestion.`,
  };
}

/**
 * The measured precision of results at this similarity score, from the
 * calibration the backend computed over the labelled queries (eval/calibrate.py).
 * Mirrors trust.calibrated_confidence in the API. Null when nothing is loaded.
 */
export function measuredConfidence(score, calibration) {
  if (score == null || !calibration?.bins) return null;
  const bin = calibration.bins.find((b) => score >= b.lo && (score < b.hi || b.hi >= 1));
  if (!bin || !bin.n) return null;
  return {
    precision: bin.precision,
    n: bin.n,
    text: `${Math.round(bin.precision * 100)}% of ${bin.n} labelled results scoring ${bin.lo.toFixed(2)}–${bin.hi.toFixed(2)} were relevant`,
  };
}

/* ============================================================
   PROOF SKETCH  (Unit 1 logic / proof layer)
   The chain of steps that produced one result, shown on demand.
   ============================================================ */

export function proofSteps(result, query, mode) {
  const { product, score } = result;
  const steps = [
    {
      step: "Query lifted",
      detail: `"${query}" accepted as the natural-language expression of an information need.`,
    },
  ];

  if (mode === "semantic") {
    steps.push({
      step: "Service invoked",
      detail: "cat:embeddingService encoded the query into a 384-dimension vector.",
    });
    steps.push({
      step: "Similarity computed",
      detail: `Cosine similarity against the product vector = ${
        score !== null && score !== undefined ? Number(score).toFixed(4) : "n/a"
      }.`,
    });
  } else {
    steps.push({
      step: "Pattern matched",
      detail: "The literal string was found in schema:name or schema:description.",
    });
  }

  if (product.category_name) {
    steps.push({
      step: "Class entailed",
      detail: `rdf:type ${product.category_name} — and therefore cat:CatalogueThing by rdfs:subClassOf.`,
    });
  }

  steps.push({
    step: "Provenance recorded",
    detail: "prov:wasDerivedFrom ex:table/products — asserted by the catalogue, not inferred.",
  });

  return steps;
}

/* ============================================================
   EXAMPLE QUERIES
   Chosen to contrast meaning against string matching, which is the
   argument the evaluation phase of the project has to make.
   ============================================================ */

export const EXAMPLE_QUERIES = [
  { text: "warm winter jacket for men", note: "paraphrase" },
  { text: "something to keep coffee hot", note: "intent, no keyword" },
  { text: "noise cancelling headphones", note: "literal" },
  { text: "gift for someone who codes", note: "vague" },
  { text: "shoes that work for flat feet", note: "descriptive" },
  { text: "kit for a first apartment kitchen", note: "compositional" },
];
