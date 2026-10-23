// Serialise a list of products with the real src/rdf.js, for external validation.
//
//   node scripts/export-graphs.mjs <products.json> <out-dir>
//
// products.json is an array of ProductOut objects as returned by the API. Writes
// all.ttl, all.rdf and all.jsonld so an independent parser (rdflib, in the
// backend tests) can check that the hand-written serialisers produce valid RDF
// and that the three syntaxes describe the same graph.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { resultsToTriples, toTurtle, toRDFXML, toJSONLD } from "../src/rdf.js";

const [, , input, outDir] = process.argv;
if (!input || !outDir) {
  console.error("usage: node export-graphs.mjs <products.json> <out-dir>");
  process.exit(2);
}

const products = JSON.parse(readFileSync(input, "utf8"));
const results = products.map((product) => ({ product, score: null }));
const triples = resultsToTriples(results);

mkdirSync(outDir, { recursive: true });
writeFileSync(join(outDir, "all.ttl"), toTurtle(triples));
writeFileSync(join(outDir, "all.rdf"), toRDFXML(triples));
writeFileSync(join(outDir, "all.jsonld"), toJSONLD(results));
console.log(`wrote ${triples.length} triples for ${products.length} products`);
