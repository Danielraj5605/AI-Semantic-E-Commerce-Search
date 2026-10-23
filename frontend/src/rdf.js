/**
 * rdf.js — the semantic layer of the application.
 *
 * The backend exposes a *relational* catalogue (products, categories, brands).
 * This module performs what Unit 4 of the syllabus calls "Exposing Relational
 * Databases": it applies a direct mapping from table rows to RDF triples over
 * well-known vocabularies (schema.org, Dublin Core, FOAF, PROV-O), and then
 * serialises that graph into the concrete syntaxes covered in Unit 5
 * (RDF/XML, Turtle, JSON-LD).
 *
 * Nothing here talks to the network. It is a pure row -> graph transformation,
 * which is the whole point: the RDF view is a *view*, not a second store.
 */

/* ============================================================
   NAMESPACES  (Unit 5 — XML namespaces / QNames)
   ============================================================ */

export const NAMESPACES = {
  rdf: "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
  rdfs: "http://www.w3.org/2000/01/rdf-schema#",
  owl: "http://www.w3.org/2002/07/owl#",
  xsd: "http://www.w3.org/2001/XMLSchema#",
  schema: "http://schema.org/",
  dcterms: "http://purl.org/dc/terms/",
  foaf: "http://xmlns.com/foaf/0.1/",
  prov: "http://www.w3.org/ns/prov#",
  cat: "http://example.org/ontology/catalog#",
  // Must equal the backend BASE_URI (trailing slash) for URIs to dereference.
  ex: import.meta.env?.VITE_BASE_URI || "http://example.org/catalog/",
};

/** Human-readable gloss for each vocabulary, shown in the prefix table. */
export const NAMESPACE_NOTES = {
  rdf: "RDF core vocabulary — rdf:type asserts class membership.",
  rdfs: "RDF Schema — rdfs:subClassOf builds the taxonomy backbone.",
  owl: "Web Ontology Language — owl:Class, owl:sameAs, cardinality.",
  xsd: "XML Schema datatypes — typed literals for price, rating, dates.",
  schema: "schema.org — the de-facto shared e-commerce vocabulary.",
  dcterms: "Dublin Core Terms — provenance and descriptive metadata.",
  foaf: "Friend of a Friend — agents and people (Unit 5 case study).",
  prov: "PROV-O — records where each assertion came from.",
  cat: "Local ontology: catalogue classes and properties.",
  ex: "Local instance namespace: one URI per catalogue resource.",
};

/* ============================================================
   TERM CONSTRUCTORS
   ============================================================ */

export const uri = (value) => ({ term: "uri", value });
export const bnode = (value) => ({ term: "bnode", value });
export const literal = (value, datatype = null, lang = null) => ({
  term: "literal",
  value: String(value),
  datatype,
  lang,
});

/** A triple is { s, p, o } where each position is a term. */
const triple = (s, p, o) => ({ s, p, o });

/* ============================================================
   IDENTITY  (Unit 1 — every resource gets a URI)
   ============================================================ */

/** Turn arbitrary text into a PascalCase local name usable as a QName. */
export function localName(text) {
  if (!text) return "Thing";
  const parts = String(text)
    // Apostrophes are dropped, not treated as separators: "Men's" must become
    // "Mens", never "MenS".
    .replace(/['’]/g, "")
    .replace(/[^A-Za-z0-9\s-]/g, " ")
    .split(/[\s-]+/)
    .filter(Boolean);
  if (!parts.length) return "Thing";
  return parts
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1).toLowerCase())
    .join("");
}

/** Slug suitable for the instance namespace (lowercase, hyphenated). */
export function slug(text) {
  return (
    String(text || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/(^-|-$)/g, "") || "unnamed"
  );
}

export const productURI = (product) => `ex:product/${product.product_id}`;
export const brandURI = (brand) => `ex:brand/${slug(brand)}`;
export const categoryURI = (name) => `cat:${localName(name)}`;

/* ============================================================
   DIRECT MAPPING RULES  (Unit 4 — exposing relational databases)
   Displayed verbatim in the Mapping panel so the documented rule
   set and the generated graph cannot drift apart.
   ============================================================ */

export const MAPPING_RULES = [
  {
    column: "products.product_id",
    predicate: "— (subject)",
    note: "Primary key becomes the resource URI ex:product/{uuid}.",
  },
  { column: "products.name", predicate: "schema:name", note: "Plain literal, language-tagged @en." },
  { column: "products.description", predicate: "schema:description", note: "Plain literal, language-tagged @en." },
  { column: "products.brand", predicate: "schema:brand", note: "Lifted into its own resource of type schema:Brand." },
  { column: "products.category_id", predicate: "schema:category / rdf:type", note: "FK resolved to an owl:Class in the local ontology." },
  { column: "products.price", predicate: "schema:offers → schema:price", note: "Reified as a schema:Offer node; xsd:decimal literal." },
  { column: "products.stock_quantity", predicate: "schema:offers → schema:availability", note: "Mapped to schema:InStock / schema:OutOfStock." },
  { column: "products.rating_avg", predicate: "schema:aggregateRating", note: "Blank node of type schema:AggregateRating." },
  { column: "products.image_url", predicate: "schema:image", note: "Object is a URI reference, not a string literal." },
  { column: "products.created_at", predicate: "dcterms:created", note: "xsd:dateTime literal." },
  { column: "(query result)", predicate: "cat:similarityScore", note: "Query-scoped annotation carrying the vector score." },
];

/* ============================================================
   ROW -> GRAPH
   ============================================================ */

/**
 * Map one product row to its RDF description.
 * @param {object} product ProductOut as returned by the API
 * @param {number|null} score similarity score for the current query, if any
 * @returns {Array} list of triples
 */
export function productToTriples(product, score = null) {
  const s = uri(productURI(product));
  const short = slug(product.product_id).slice(0, 8);
  const offer = bnode(`offer-${short}`);
  const rating = bnode(`rating-${short}`);
  const out = [];

  out.push(triple(s, uri("rdf:type"), uri("schema:Product")));
  if (product.category_name) {
    out.push(triple(s, uri("rdf:type"), uri(categoryURI(product.category_name))));
    out.push(triple(s, uri("schema:category"), uri(categoryURI(product.category_name))));
  }
  if (product.name) out.push(triple(s, uri("schema:name"), literal(product.name, null, "en")));
  if (product.description) {
    out.push(triple(s, uri("schema:description"), literal(product.description, null, "en")));
  }
  if (product.brand) {
    out.push(triple(s, uri("schema:brand"), uri(brandURI(product.brand))));
    out.push(triple(uri(brandURI(product.brand)), uri("rdf:type"), uri("schema:Brand")));
    out.push(triple(uri(brandURI(product.brand)), uri("schema:name"), literal(product.brand)));
  }
  if (product.image_url) out.push(triple(s, uri("schema:image"), uri(product.image_url)));

  if (product.price !== null && product.price !== undefined) {
    out.push(triple(s, uri("schema:offers"), offer));
    out.push(triple(offer, uri("rdf:type"), uri("schema:Offer")));
    out.push(triple(offer, uri("schema:price"), literal(Number(product.price).toFixed(2), "xsd:decimal")));
    out.push(triple(offer, uri("schema:priceCurrency"), literal("USD")));
    out.push(
      triple(
        offer,
        uri("schema:availability"),
        uri(product.stock_quantity > 0 ? "schema:InStock" : "schema:OutOfStock")
      )
    );
  }

  if (product.rating_avg) {
    out.push(triple(s, uri("schema:aggregateRating"), rating));
    out.push(triple(rating, uri("rdf:type"), uri("schema:AggregateRating")));
    out.push(
      triple(rating, uri("schema:ratingValue"), literal(Number(product.rating_avg).toFixed(1), "xsd:decimal"))
    );
    out.push(triple(rating, uri("schema:bestRating"), literal("5.0", "xsd:decimal")));
  }

  if (product.created_at) {
    out.push(triple(s, uri("dcterms:created"), literal(product.created_at, "xsd:dateTime")));
  }

  out.push(triple(s, uri("prov:wasDerivedFrom"), uri("ex:table/products")));

  if (score !== null && score !== undefined) {
    out.push(triple(s, uri("cat:similarityScore"), literal(Number(score).toFixed(4), "xsd:double")));
  }

  return out;
}

/** Map a whole result set to a single de-duplicated graph. */
export function resultsToTriples(results = []) {
  const seen = new Set();
  const graph = [];
  for (const r of results) {
    for (const t of productToTriples(r.product, r.score)) {
      const key = `${t.s.value}|${t.p.value}|${t.o.value}`;
      if (seen.has(key)) continue;
      seen.add(key);
      graph.push(t);
    }
  }
  return graph;
}

/* ============================================================
   SERIALISATION  (Unit 5 — concrete syntaxes)
   ============================================================ */

const escapeLiteral = (v) =>
  v.replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\n/g, "\\n");

const expand = (qname) => {
  const idx = qname.indexOf(":");
  if (idx < 0) return qname;
  const prefix = qname.slice(0, idx);
  if (!NAMESPACES[prefix]) return qname; // already an absolute URI (http:, https:)
  return NAMESPACES[prefix] + qname.slice(idx + 1);
};

/**
 * Turtle's PN_LOCAL production does not admit "/", so `ex:product/{uuid}` is a
 * fine label for a human but is not a legal QName. Anything that will not
 * survive as a prefixed name is written out as a full IRI instead — the UI can
 * go on showing the short form, but what we serialise has to actually parse.
 */
const isLegalQName = (v) => /^[A-Za-z][A-Za-z0-9_-]*:[A-Za-z0-9_][A-Za-z0-9_.-]*$/.test(v);

const termToTurtle = (t) => {
  if (t.term === "uri") {
    if (t.value.startsWith("http")) return `<${t.value}>`;
    return isLegalQName(t.value) ? t.value : `<${expand(t.value)}>`;
  }
  if (t.term === "bnode") return `_:${t.value}`;
  let s = `"${escapeLiteral(t.value)}"`;
  if (t.datatype) s += `^^${t.datatype}`;
  else if (t.lang) s += `@${t.lang}`;
  return s;
};

/** Group triples by subject, preserving insertion order. */
function groupBySubject(triples) {
  const groups = new Map();
  for (const t of triples) {
    const key = `${t.s.term}:${t.s.value}`;
    if (!groups.has(key)) groups.set(key, { subject: t.s, triples: [] });
    groups.get(key).triples.push(t);
  }
  return [...groups.values()];
}

/** Which prefixes does this graph actually use? Keeps the headers honest. */
function usedPrefixes(triples) {
  const used = new Set();
  const scan = (t) => {
    if (t.term === "literal") {
      if (t.datatype) used.add(t.datatype.split(":")[0]);
      return;
    }
    if (t.term !== "uri") return;
    const p = t.value.split(":")[0];
    if (NAMESPACES[p]) used.add(p);
  };
  triples.forEach((t) => [t.s, t.p, t.o].forEach(scan));
  return [...used].sort();
}

export function toTurtle(triples) {
  if (!triples.length) return "# empty graph";
  const header = usedPrefixes(triples)
    .map((p) => `@prefix ${p}: <${NAMESPACES[p]}> .`)
    .join("\n");

  const body = groupBySubject(triples)
    .map(({ subject, triples: ts }) => {
      const lines = ts.map(
        (t, i) => `    ${termToTurtle(t.p)} ${termToTurtle(t.o)}${i === ts.length - 1 ? " ." : " ;"}`
      );
      return `${termToTurtle(subject)}\n${lines.join("\n")}`;
    })
    .join("\n\n");

  return `${header}\n\n${body}\n`;
}

const escapeXML = (v) =>
  v
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

export function toRDFXML(triples) {
  if (!triples.length) return "<!-- empty graph -->";
  const nsDecls = usedPrefixes(triples)
    .filter((p) => p !== "rdf")
    .map((p) => `         xmlns:${p}="${NAMESPACES[p]}"`)
    .join("\n");

  const body = groupBySubject(triples)
    .map(({ subject, triples: ts }) => {
      const about =
        subject.term === "bnode"
          ? ` rdf:nodeID="${subject.value}"`
          : ` rdf:about="${escapeXML(expand(subject.value))}"`;

      const props = ts
        .map((t) => {
          const tag = t.p.value;
          if (t.o.term === "uri") {
            return `    <${tag} rdf:resource="${escapeXML(expand(t.o.value))}"/>`;
          }
          if (t.o.term === "bnode") {
            return `    <${tag} rdf:nodeID="${t.o.value}"/>`;
          }
          const attr = t.o.datatype
            ? ` rdf:datatype="${escapeXML(expand(t.o.datatype))}"`
            : t.o.lang
            ? ` xml:lang="${t.o.lang}"`
            : "";
          return `    <${tag}${attr}>${escapeXML(t.o.value)}</${tag}>`;
        })
        .join("\n");

      return `  <rdf:Description${about}>\n${props}\n  </rdf:Description>`;
    })
    .join("\n\n");

  return `<?xml version="1.0" encoding="UTF-8"?>\n<rdf:RDF xmlns:rdf="${NAMESPACES.rdf}"\n${nsDecls}>\n\n${body}\n\n</rdf:RDF>\n`;
}

/**
 * JSON-LD is built structurally rather than from the flat triple list, because
 * its whole advantage is that the tree shape survives — this is the form that
 * actually gets embedded in the page for crawlers.
 */
export function toJSONLD(results = []) {
  // `name` and `description` carry @en, exactly as the Turtle and RDF/XML do.
  // Anything that must stay a plain literal (a brand's name) uses the prefixed
  // key `schema:name`, which this context entry does not affect.
  const context = {
    schema: NAMESPACES.schema,
    dcterms: NAMESPACES.dcterms,
    cat: NAMESPACES.cat,
    prov: NAMESPACES.prov,
    xsd: NAMESPACES.xsd,
    name: { "@id": "schema:name", "@language": "en" },
    description: { "@id": "schema:description", "@language": "en" },
    image: { "@id": "schema:image", "@type": "@id" },
  };
  const typed = (value, type) => ({ "@value": value, "@type": type });

  const graph = results.map(({ product, score }) => {
    const types = ["schema:Product"];
    if (product.category_name) types.push(categoryURI(product.category_name));

    const node = {
      "@id": `${NAMESPACES.ex}product/${product.product_id}`,
      "@type": types,
      name: product.name,
    };
    if (product.description) node.description = product.description;
    if (product.image_url) node.image = product.image_url;
    if (product.brand) {
      // The brand is a resource with its own URI, as in the other syntaxes.
      node["schema:brand"] = {
        "@id": `${NAMESPACES.ex}brand/${slug(product.brand)}`,
        "@type": "schema:Brand",
        "schema:name": product.brand,
      };
    }
    if (product.category_name) {
      node["schema:category"] = { "@id": categoryURI(product.category_name) };
    }
    if (product.price !== null && product.price !== undefined) {
      node["schema:offers"] = {
        "@type": "schema:Offer",
        "schema:price": typed(Number(product.price).toFixed(2), "xsd:decimal"),
        "schema:priceCurrency": "USD",
        "schema:availability": {
          "@id": product.stock_quantity > 0 ? "schema:InStock" : "schema:OutOfStock",
        },
      };
    }
    if (product.rating_avg) {
      node["schema:aggregateRating"] = {
        "@type": "schema:AggregateRating",
        "schema:ratingValue": typed(Number(product.rating_avg).toFixed(1), "xsd:decimal"),
        "schema:bestRating": typed("5.0", "xsd:decimal"),
      };
    }
    if (product.created_at) {
      node["dcterms:created"] = typed(product.created_at, "xsd:dateTime");
    }
    if (score !== null && score !== undefined) {
      node["cat:similarityScore"] = typed(Number(score).toFixed(4), "xsd:double");
    }
    node["prov:wasDerivedFrom"] = { "@id": `${NAMESPACES.ex}table/products` };
    return node;
  });

  return JSON.stringify({ "@context": context, "@graph": graph }, null, 2);
}

/* ============================================================
   SPARQL  (Unit 5 — addressing and querying)
   Renders the *equivalent* SPARQL for whatever the user has asked
   for through the UI, so the query language stays visible.
   ============================================================ */

export function buildSPARQL(query, filters = {}, mode = "semantic") {
  const q = String(query || "").replace(/"/g, '\\"');
  const prefixes = ["rdf", "rdfs", "schema", "cat"]
    .map((p) => `PREFIX ${p}: <${NAMESPACES[p]}>`)
    .join("\n");

  const where = [
    "  ?product rdf:type            schema:Product ;",
    "           schema:name         ?name ;",
    "           schema:description  ?description .",
    "  OPTIONAL { ?product schema:brand/schema:name ?brand . }",
    "  OPTIONAL { ?product schema:offers/schema:price ?price . }",
    "  OPTIONAL { ?product schema:aggregateRating/schema:ratingValue ?rating . }",
  ];

  if (filters.category) {
    where.push(`  ?product schema:category ${categoryURI(filters.category)} .`);
  }
  if (filters.brand) {
    where.push(`  ?product schema:brand/schema:name "${filters.brand}" .`);
  }
  if (filters.min_price) where.push(`  FILTER (?price >= ${Number(filters.min_price)})`);
  if (filters.max_price) where.push(`  FILTER (?price <= ${Number(filters.max_price)})`);
  if (filters.min_rating) where.push(`  FILTER (?rating >= ${Number(filters.min_rating)})`);

  if (mode === "semantic") {
    where.push("");
    where.push("  # Similarity is a service invocation, not a graph pattern:");
    where.push("  # the vector index answers it and binds ?score.");
    where.push("  SERVICE cat:embeddingService {");
    where.push(`    ?product cat:matches          "${q}" ;`);
    where.push("             cat:similarityScore  ?score .");
    where.push("  }");
  } else {
    where.push("");
    where.push(`  FILTER (CONTAINS(LCASE(?name), LCASE("${q}"))`);
    where.push(`       || CONTAINS(LCASE(?description), LCASE("${q}")))`);
  }

  const order = mode === "semantic" ? "ORDER BY DESC(?score)" : "ORDER BY ?name";
  const select =
    mode === "semantic"
      ? "SELECT ?product ?name ?brand ?price ?rating ?score"
      : "SELECT ?product ?name ?brand ?price ?rating";

  return `${prefixes}\n\n${select}\nWHERE {\n${where.join("\n")}\n}\n${order}\nLIMIT ${filters.limit || 40}`;
}

/* ============================================================
   ONTOLOGY  (Unit 2 — classes and subClassOf)
   ============================================================ */

/**
 * Build a class tree out of the flat category list returned by /api/filters.
 * Each category is presented as an owl:Class; the FK becomes rdfs:subClassOf.
 */
export function buildClassTree(categories = []) {
  const byId = new Map();
  categories.forEach((c) =>
    byId.set(c.category_id, { ...c, qname: categoryURI(c.name), children: [] })
  );

  const roots = [];
  byId.forEach((node) => {
    const parent = node.parent_category_id != null ? byId.get(node.parent_category_id) : null;
    if (parent && parent !== node) parent.children.push(node);
    else roots.push(node);
  });

  const sortRec = (nodes) => {
    nodes.sort((a, b) => a.name.localeCompare(b.name));
    nodes.forEach((n) => sortRec(n.children));
  };
  sortRec(roots);
  return roots;
}

/** Axioms describing the local ontology, rendered in the ontology panel. */
export function ontologyAxioms(classTree = []) {
  const axioms = [
    { subject: "cat:CatalogueThing", predicate: "rdf:type", object: "owl:Class" },
    { subject: "schema:Product", predicate: "rdfs:subClassOf", object: "cat:CatalogueThing" },
    { subject: "cat:similarityScore", predicate: "rdf:type", object: "owl:DatatypeProperty" },
    { subject: "cat:similarityScore", predicate: "rdfs:range", object: "xsd:double" },
    { subject: "schema:brand", predicate: "rdf:type", object: "owl:ObjectProperty" },
    { subject: "schema:brand", predicate: "rdfs:range", object: "schema:Brand" },
  ];

  const walk = (nodes, parentQ) => {
    nodes.forEach((n) => {
      axioms.push({ subject: n.qname, predicate: "rdf:type", object: "owl:Class" });
      axioms.push({
        subject: n.qname,
        predicate: "rdfs:subClassOf",
        object: parentQ || "cat:CatalogueThing",
      });
      walk(n.children, n.qname);
    });
  };
  walk(classTree, null);
  return axioms;
}
