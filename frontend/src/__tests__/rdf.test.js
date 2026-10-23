import { describe, it, expect } from "vitest";
import {
  productToTriples, resultsToTriples, toTurtle, toRDFXML, toJSONLD,
  buildSPARQL, buildClassTree, ontologyAxioms, NAMESPACES,
} from "../rdf.js";

const product = {
  product_id: "8f3a1c2e-0000-4000-8000-000000000001",
  name: "Insulated \"Parka\" & Co",
  description: "Warm jacket",
  category_name: "Mens Outerwear",
  brand: "Northline",
  price: 189,
  stock_quantity: 3,
  rating_avg: 4.6,
  created_at: "2025-01-02T10:00:00Z",
};
const results = [{ product, score: 0.8134 }];

describe("productToTriples", () => {
  const ts = productToTriples(product, 0.8134);
  const has = (p, o) => ts.some((t) => t.p.value === p && (o === undefined || t.o.value === o));

  it("types the product and its category class", () => {
    expect(has("rdf:type", "schema:Product")).toBe(true);
    expect(ts.filter((t) => t.p.value === "rdf:type").length).toBeGreaterThanOrEqual(2);
  });
  it("reifies price as an Offer and rating as an AggregateRating", () => {
    expect(has("schema:offers")).toBe(true);
    expect(has("schema:price")).toBe(true);
    expect(has("schema:aggregateRating")).toBe(true);
  });
  it("marks availability from stock", () => {
    expect(has("schema:availability", "schema:InStock")).toBe(true);
    const out = productToTriples({ ...product, stock_quantity: 0 });
    expect(out.some((t) => t.o.value === "schema:OutOfStock")).toBe(true);
  });
  it("annotates the query-scoped score only when given one", () => {
    expect(has("cat:similarityScore")).toBe(true);
    expect(productToTriples(product).some((t) => t.p.value === "cat:similarityScore")).toBe(false);
  });
  it("records provenance", () => expect(has("prov:wasDerivedFrom")).toBe(true));
});

describe("resultsToTriples", () => {
  it("de-duplicates triples across results", () => {
    const g = resultsToTriples([...results, ...results]);
    expect(g.length).toBe(resultsToTriples(results).length);
  });
});

describe("serialisers", () => {
  const g = resultsToTriples(results);

  it("Turtle declares only used prefixes and ends statements with a dot", () => {
    const ttl = toTurtle(g);
    expect(ttl).toContain(`@prefix schema: <${NAMESPACES.schema}> .`);
    expect(ttl).not.toContain("@prefix foaf:");
    expect(ttl.trim().endsWith(".")).toBe(true);
  });
  it("Turtle escapes quotes in literals", () => {
    expect(toTurtle(g)).toContain('\\"Parka\\"');
  });
  it("Turtle never emits a QName with a slash in the local part", () => {
    expect(toTurtle(g)).not.toMatch(/\bex:product\//);
  });
  it("RDF/XML escapes markup and is well-formed", () => {
    const xml = toRDFXML(g);
    expect(xml).toContain("&amp;");
    const doc = new DOMParser().parseFromString(xml, "application/xml");
    expect(doc.getElementsByTagName("parsererror").length).toBe(0);
  });
  it("JSON-LD is valid JSON with a context and one node per result", () => {
    const ld = JSON.parse(toJSONLD(results));
    expect(ld["@context"]).toBeTruthy();
    expect(ld["@graph"]).toHaveLength(1);
    expect(ld["@graph"][0]["@type"]).toEqual(["schema:Product", "cat:MensOuterwear"]);
  });
  it("empty graphs serialise to a comment, not an error", () => {
    expect(toTurtle([])).toBe("# empty graph");
    expect(toRDFXML([])).toBe("<!-- empty graph -->");
  });
});

describe("buildSPARQL", () => {
  it("semantic mode uses a SERVICE block and orders by score", () => {
    const q = buildSPARQL("warm jacket", {}, "semantic");
    expect(q).toContain("SERVICE cat:embeddingService");
    expect(q).toContain("ORDER BY DESC(?score)");
  });
  it("keyword mode uses CONTAINS filters and no SERVICE", () => {
    const q = buildSPARQL("jacket", {}, "keyword");
    expect(q).toContain("CONTAINS");
    expect(q).not.toContain("SERVICE");
  });
  it("renders constraints as graph patterns and FILTERs", () => {
    const q = buildSPARQL("x", { category: "Mens Outerwear", min_price: 10, max_price: 50, min_rating: 4 });
    expect(q).toContain("schema:category cat:");
    expect(q).toContain("FILTER (?price >= 10)");
    expect(q).toContain("FILTER (?price <= 50)");
    expect(q).toContain("FILTER (?rating >= 4)");
  });
  it("escapes quotes in the query", () => {
    expect(buildSPARQL('say "hi"')).toContain('say \\"hi\\"');
  });
});

describe("class tree", () => {
  const cats = [
    { category_id: 1, name: "Clothing", parent_category_id: null },
    { category_id: 2, name: "Jackets", parent_category_id: 1 },
    { category_id: 3, name: "Shoes", parent_category_id: null },
  ];
  it("nests children under parents and keeps roots sorted", () => {
    const tree = buildClassTree(cats);
    expect(tree.map((n) => n.name)).toEqual(["Clothing", "Shoes"]);
    expect(tree[0].children[0].name).toBe("Jackets");
  });
  it("emits subClassOf axioms down to the root", () => {
    const ax = ontologyAxioms(buildClassTree(cats));
    expect(ax).toContainEqual({ subject: "cat:Jackets", predicate: "rdfs:subClassOf", object: "cat:Clothing" });
    expect(ax).toContainEqual({ subject: "cat:Clothing", predicate: "rdfs:subClassOf", object: "cat:CatalogueThing" });
  });
  it("survives a self-referencing parent", () => {
    expect(buildClassTree([{ category_id: 1, name: "A", parent_category_id: 1 }]).length).toBe(1);
  });
});
