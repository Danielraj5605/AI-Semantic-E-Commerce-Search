# CatalogueGraph

**A product catalogue published as a knowledge graph — and searched by meaning.**

Course project for **21CSE452T · Semantic Web** (Professional Elective, School of Computing).

The rows live in PostgreSQL. Everything the interface shows is a *view over them in RDF*: every
product carries a URI, is typed against an OWL class hierarchy, describes itself in schema.org
terms, records where its facts came from, and can be exported as Turtle, RDF/XML or JSON-LD.
Retrieval is done by vector similarity, and the interface is explicit about the difference between
what it *asserts* and what it merely *believes*.

---

## What makes this a Semantic Web project

A vector search engine is not, on its own, a Semantic Web application — "semantic" in
`sentence-transformers` means statistical similarity, not the formal semantics of RDF and OWL. The
two share a word and very little else.

This project pairs them deliberately, and the interface is built to make the pairing legible:

| Syllabus unit | Topic | Where it is in the app |
|---|---|---|
| **Unit 1** — The Semantic Web | Layer cake · RDF · properties · visualisation · annotation · searching strategies | Layer-cake panel, triple table on every result, node-link RDF graph, JSON-LD annotation injected into the document head |
| **Unit 2** — Understanding Ontologies | Syntax · structure · semantics · pragmatics · OWL · levels of ontologies | The left rail is an **ontology browser**: the class tree, its QNames, and its axioms — browsing the ontology and filtering the results are the same gesture |
| **Unit 3** — Semantic Web Services | Invoking · describing · finding services · agents · distributed trust and belief | The **service descriptor strip** names the service invoked and its binding; each result carries a stated **degree of belief** with its basis |
| **Unit 4** — Ontology Engineering | Reusing ontologies · ontology mapping · exposing relational databases | The **Mapping** panel lists the column-by-column direct-mapping rules that lift SQL rows into the graph — the same rules the code applies |
| **Unit 5** — Case Studies with XML | XML · structuring · namespaces · addressing and querying · FOAF | **Serialisation tabs** (Turtle / RDF-XML / JSON-LD) over the live result set, the prefix table, and the equivalent **SPARQL** for whatever you asked |

### The layer cake, honestly labelled

| Layer | State | What this app does at that level |
|---|---|---|
| URI / Unicode | ✅ full | Every product, brand and class has a URI in the `ex:` / `cat:` namespaces |
| XML + Namespaces | ✅ full | RDF/XML output with prefixed vocabularies; no term collides |
| RDF | ✅ full | Each catalogue row lifted into triples over schema.org and Dublin Core |
| RDF Schema | ✅ full | Categories become `owl:Class` nodes joined by `rdfs:subClassOf` |
| Ontology (OWL) | ✅ full | A real OWL ontology (`GET /api/ontology`): class tree, disjointness, domain/range, an inverse property, cardinality restrictions, and defined classes (`TopRated`, `Premium`, `InStockProduct`) as `owl:equivalentClass` |
| Logic | ✅ full | A forward-chaining reasoner applies six RDFS/OWL-RL rules to every product and five consistency checks to the whole catalogue (`GET /api/ontology/validate`) |
| Proof | ✅ full | Every inferred fact has a proof tree (rule, premises, down to catalogue rows and ontology axioms): `GET /api/product/{id}/proof`, or **Reasoning** on any result |
| Trust | ✅ full | PROV-O provenance per product and inference; match confidence **measured** from the evaluation; HMAC-signed canonical digest that detects a single altered triple |

"Full" means complete for this application's scope, and the scope is stated: the reasoner is rule-based
(OWL 2 RL style), not an OWL DL tableau prover. It has no open-world satisfiability checking, property chains
or negation, none of which a product catalogue needs. See [The upper layers](#the-upper-layers) below.

---

## Interface

- **Landing** — the catalogue framed as a graph, with the layer cake and a sample Turtle description.
- **Ontology rail** — class tree (`owl:Class` + `rdfs:subClassOf`), brands as `schema:Brand`
  individuals, and typed-literal constraints that read as SPARQL `FILTER` clauses.
- **Resource cards** — announced by URI, not by product name. Each expands into:
  - **Triples** — the full subject-omitted predicate/object table
  - **Graph** — an inline-SVG star of the resource's properties
  - **Why this?** — the proof trace, and the basis of the stated belief
- **Answer graph** — the whole result set clustered by entailed class, node size encoding
  `cat:similarityScore`.
- **Inspector drawer** — Turtle · RDF/XML · JSON-LD · SPARQL · Mapping · Axioms · Prefixes, all over
  the live result set.
- **Meaning / Strings toggle** — the same query through the vector service and through plain SQL
  `ILIKE`, which is the comparison the evaluation phase has to make.

Colour is used as a type system throughout — teal for resources, indigo for classes, amber for
literals, violet for blank nodes, slate for predicates — consistently in tables, graph nodes and
serialisation panes.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Browser — React 19 + Vite            localhost:5173         │
│                                                              │
│   src/rdf.js       relational row  ──►  RDF triples          │
│                    triples  ──►  Turtle / RDF-XML / JSON-LD  │
│                    UI state ──►  equivalent SPARQL           │
│   src/concepts.js  layer cake · unit map · trust · proof     │
└───────────────────────────┬──────────────────────────────────┘
                            │  HTTP REST (JSON)
┌───────────────────────────▼──────────────────────────────────┐
│  FastAPI                              localhost:8000         │
│    /api/search        encode query → cosine similarity       │
│    /api/search/keyword  SQL ILIKE baseline & fallback        │
│    /api/autocomplete  · /api/filters · /health · /docs       │
└───────────────────────────┬──────────────────────────────────┘
                            │  asyncpg / SQLAlchemy 2.0 (async)
┌───────────────────────────▼──────────────────────────────────┐
│  PostgreSQL (Neon.tech) + pgvector                           │
│    products ─ product_embeddings (384-dim) ─ categories      │
│    product_images ─ users ─ search_logs                      │
└──────────────────────────────────────────────────────────────┘
```

**The graph is a view, not a second store.** There is no triple store to keep in sync: `src/rdf.js`
is a pure row→graph transformation applied at render time. This is exactly the "Exposing Relational
Databases" approach from Unit 4, and it is why the RDF can never drift from the SQL.

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite 5, vanilla CSS (no framework) |
| RDF layer | Hand-written — no library; ~450 lines in `src/rdf.js` |
| Vocabularies | schema.org, RDF/RDFS, OWL, XSD, Dublin Core Terms, FOAF, PROV-O |
| Backend | FastAPI 0.115, Python 3.11+ |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL (Neon.tech) + `pgvector` |
| Embeddings | `sentence-transformers` — `all-MiniLM-L6-v2` (384-dim, local, free) |
| Caching | `cachetools` TTLCache (5 min, in-memory; degraded answers are never cached) |
| RDF cross-check | `rdflib` (server-side Linked Data and test oracle) |

---

## Getting started

### Prerequisites

- Python 3.11+
- Node.js 18+
- **Either** a [Neon.tech](https://neon.tech) PostgreSQL database with the `pgvector` extension,
  **or** nothing at all: set `USE_LOCAL_DB=true` and the app uses a SQLite file
  (`backend/catalogue.db`), ranking by cosine similarity in Python. Fine for a demo-sized catalogue.

### 1. Clone

```bash
git clone https://github.com/Danielraj5605/AI-Semantic-E-Commerce-Search.git
cd AI-Semantic-E-Commerce-Search
```

### 2. Backend

```bash
cd backend

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

pip install -r requirements.txt

cp .env.example .env
# edit .env and fill in DATABASE_URL from Neon.tech
```

### 3. Database

```bash
python scripts/migrate.py             # create tables, enable pgvector
python scripts/load_data.py           # import products from data/
python scripts/generate_embeddings.py # embed the whole catalogue
python scripts/set_category_hierarchy.py  # give categories parents (rdfs:subClassOf); safe to re-run
python scripts/clear_dead_image_urls.py   # optional: null out image URLs that 404 (--dry-run to preview)
python scripts/set_product_images.py     # optional: replacement photos for the 7 products whose original links were deleted
```

### 4. Run

```bash
# backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# frontend (separate terminal)
cd frontend && npm install && npm run dev
```

- App → **http://localhost:5173**
- API docs → **http://localhost:8000/docs**

### Or with Docker

```bash
docker compose up --build      # frontend :8080, backend :8000
```

The backend image bakes in the embedding model, so it starts without network access. By default
it serves `backend/catalogue.db` (build it first with the scripts above); for Neon, put
`USE_LOCAL_DB=false`, `DATABASE_URL` and `DATABASE_URL_SYNC` in a `.env` beside
`docker-compose.yml`. Compose sets `BASE_URI` so product URIs are the URLs that serve them.
*The Docker files have not been built on the author's machine (no Docker installed there);
if the build fails, please report it.*

### Tests

```bash
cd backend  && pip install -r requirements-dev.txt && pytest     # API, reliability, RDF interop, evaluation guards
cd frontend && npm test                                         # rdf.js serialisers and SPARQL
```

Backend tests run against a temporary copy of `catalogue.db`, so they never modify your data; they
skip when the file is absent (as in CI).

---

## API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/search?q=…` | Semantic search with optional filters |
| `GET` | `/api/search/keyword?q=…` | Keyword-only baseline / fallback |
| `GET` | `/api/autocomplete?q=…` | Prefix suggestions on product names |
| `GET` | `/api/filters` | Categories, brands, price range — the raw material for the class tree |
| `GET` | `/api/product/{id}` | One product. `Accept: text/turtle`, `application/rdf+xml` or `application/ld+json` (or `?format=ttl\|rdf\|jsonld`) returns its RDF description; otherwise JSON |
| `GET` | `/api/product/{id}/similar` | Nearest products by stored embedding (works with the encoder down) |
| `POST` | `/api/click` | Record that a result was opened (`{query, product_id}`). With `CLICK_BOOST_WEIGHT` > 0 these clicks nudge popular products up the semantic ranking (global popularity, not per-user; reported scores are unchanged) |
| `POST/PUT/DELETE` | `/api/admin/products[/{id}]` | Add / update / delete a product and re-embed it. **Only mounted when `ADMIN_TOKEN` is set**; send it as `X-Admin-Token` |
| `GET` | `/api/ontology` | The OWL ontology: JSON summary, or Turtle / RDF-XML / JSON-LD by `Accept` or `?format=` |
| `GET` | `/api/ontology/validate` | Entail the whole catalogue and check it against the ontology: conformance, inferred-triple counts, violations |
| `GET` | `/api/product/{id}/inferences` | What follows from this product plus the ontology (JSON, or RDF of asserted + inferred) |
| `GET` | `/api/product/{id}/proof` | A proof tree for every inferred fact about the product |
| `GET` | `/api/product/{id}/provenance` | PROV-O provenance plus a signed digest (`X-Content-Digest` / `X-Content-Signature` in RDF mode) |
| `POST` | `/api/verify` | `{turtle, signature, product_id?}`: is this graph exactly what was signed, and does it still match the catalogue? |
| `GET` | `/api/trust/calibration` | Measured precision of results by similarity score |
| `GET` | `/api/logic/rules` | The rules the reasoner applies |
| `GET` | `/health` | Component state: database and embedding model (503 only if the database is down) |

### Linked Data

Set `BASE_URI=http://localhost:8000/api/` and every product URI becomes the URL that serves it:

```bash
curl -H 'Accept: text/turtle' http://localhost:8000/api/product/<uuid>
```
| `GET` | `/docs` | Swagger UI |

### Search parameters

| Param | Type | Description |
|---|---|---|
| `q` | `string` | Query (required) |
| `category` | `string` | Class constraint — becomes a `schema:category` graph pattern |
| `brand` | `string` | Brand constraint |
| `min_price` / `max_price` | `float` | Become SPARQL `FILTER` clauses on `xsd:decimal` |
| `min_rating` | `float` | 0–5 |
| `limit` / `offset` | `int` | Pagination (limit default 20, max 100) |

---

## The upper layers

**Ontology.** `app/semantics/ontology.py` builds the OWL document from the `categories` table plus a small table of
properties, restrictions and defined classes. A defined class is stored the OWL way, for example
`cat:Premium owl:equivalentClass [ owl:intersectionOf ( schema:Product [ owl:onProperty schema:offers; owl:someValuesFrom [ owl:onProperty schema:price; owl:someValuesFrom [ owl:onDatatype xsd:decimal; owl:withRestrictions ( [ xsd:minInclusive 200.0 ] ) ] ] ] ) ]`,
and the reasoner reads it back from the graph, so the document and the behaviour cannot drift apart.

**Logic.** `app/semantics/reasoner.py` applies `scm-sco`, `cax-sco`, `prp-dom`, `prp-rng`, `prp-inv` and `cls-def` until
nothing new follows, and checks `cax-dw` (disjoint classes), `cls-card`, `dt-range`, `dt-bound`, `cls-decl`. Membership of
`TopRated`, `Premium` and `InStockProduct` is inferred, never stored. The test suite checks the closure against an
independent SPARQL property-path oracle.

**Proof.** Each derived triple records its rule and premises, so `app/semantics/proof.py` can unfold it into a tree whose
leaves are catalogue rows or ontology axioms. A fact the reasoner did not derive has no proof.

**Trust** answers three different questions with three mechanisms:

| Question | Mechanism |
|---|---|
| Where did it come from? | PROV-O graph: the entity, the mapping activity and agent, and a reified statement for each inference naming its rule |
| How much should I believe it? | Asserted rows and deductive inferences are certain *relative to the catalogue*. The only probabilistic claim, "this matches your query", gets its confidence from `eval/calibration.json`: measured precision per similarity bin (`python -m eval.calibrate`), smoothed to be monotone. It is a lower bound, since only labelled products count as relevant |
| Has it been altered? | SHA-256 over the canonical (blank-node-relabelled) N-Triples, signed with HMAC-SHA256. Set `TRUST_KEY`; without it a public development key is used and the response says so |

Re-run `python -m eval.calibrate` whenever the model, the catalogue or the labels change.

## How a row becomes a graph

```
products row
    ↓  direct mapping (src/rdf.js)
<http://example.org/catalog/product/8f3a…>
    rdf:type            schema:Product ;
    rdf:type            cat:MensOuterwear ;
    schema:name         "Insulated Parka"@en ;
    schema:brand        <…/brand/northline> ;
    schema:offers       [ a schema:Offer ;
                          schema:price "189.00"^^xsd:decimal ;
                          schema:availability schema:InStock ] ;
    schema:aggregateRating [ a schema:AggregateRating ;
                             schema:ratingValue "4.6"^^xsd:decimal ] ;
    dcterms:created     "2025-01-02T10:00:00Z"^^xsd:dateTime ;
    cat:similarityScore "0.8134"^^xsd:double ;
    prov:wasDerivedFrom <…/table/products> .
```

Note the last two lines. The similarity score is a *query-scoped annotation*, not a property of the
product — it is only true relative to the query that produced it. And the provenance statement means
the claim can be traced rather than taken on faith, which is the whole of Unit 3's argument about
distributed trust.

### And how it becomes an answer

```
"something to keep coffee hot"
        ↓  cat:embeddingService — all-MiniLM-L6-v2
[0.03, -0.14, 0.87, …]   (384 numbers)
        ↓  pgvector <=> operator (cosine distance)
nearest products in 384-dimensional space
        ↓  class + literal constraints applied
        ↓  lifted to RDF, belief band attached
ranked resources, each with a proof trace
```

---

## Project structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI entry point
│   │   ├── config.py                  # settings from .env
│   │   ├── api/search.py              # search routes, click logging, TTL cache
│   │   ├── api/products.py            # /product/{id}: content negotiation, similar
│   │   ├── api/semantics.py           # ontology, inferences, proofs, provenance, verify
│   │   ├── semantics/                 # ontology.py, reasoner.py, proof.py, trust.py
│   │   ├── api/admin.py               # product CRUD (mounted only if ADMIN_TOKEN set)
│   │   ├── db/session.py              # async SQLAlchemy session
│   │   ├── models/
│   │   │   ├── models.py              # ORM models
│   │   │   └── schemas.py             # Pydantic response schemas
│   │   └── services/
│   │       ├── embedding_service.py   # MiniLM wrapper, cache-first load, failure cool-down
│   │       ├── search_service.py      # semantic + keyword search, subclass entailment
│   │       └── rdf_service.py         # row -> RDF via rdflib (mirrors frontend/src/rdf.js)
│   └── scripts/
│       ├── migrate.py · load_data.py · set_category_hierarchy.py
│       ├── generate_embeddings.py · validate_search.py
│   ├── eval/                          # labelled queries, metrics, run_eval.py, RESULTS.md
│   └── tests/                         # pytest: API, reliability, products, RDF interop, eval
├── frontend/
│   ├── index.html                     # DC metadata + WebApplication JSON-LD
│   └── src/
│       ├── App.jsx                    # shell, state, JSON-LD embedding
│       ├── api.js                     # REST client
│       ├── rdf.js                     # ★ the semantic layer
│       ├── concepts.js                # layer cake · units · trust · proof
│       ├── index.css                  # design system (light + dark)
│       └── components/
│           ├── SearchBar.jsx          # debounced ?query binding
│           ├── OntologyRail.jsx       # class tree + constraints
│           ├── ResourceCard.jsx       # URI · triples · graph · proof
│           ├── GraphView.jsx          # inline-SVG RDF visualisation
│           ├── Inspector.jsx          # serialisation + SPARQL + mapping
│           ├── LayerCake.jsx          # layer cake + syllabus map
│           └── Term.jsx               # one RDF term, coloured by kind
├── docker-compose.yml · DEMO.md
├── data/                              # (gitignored) source catalogue
├── implementation_plan.md
└── README.md
```

---

## Environment variables

Copy `backend/.env.example` to `backend/.env`:

```env
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST/DBNAME?ssl=require
DATABASE_URL_SYNC=postgresql+psycopg2://USER:PASSWORD@HOST/DBNAME?sslmode=require
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
FRONTEND_URL=http://localhost:5173
USE_LOCAL_DB=false                       # true = SQLite file instead of Postgres
# CLICK_BOOST_WEIGHT=0.1                 # re-rank by click popularity; 0 (default) = off
BASE_URI=http://example.org/catalog/     # set to http://localhost:8000/api/ for dereferenceable URIs
# ADMIN_TOKEN=change-me                  # set to mount /api/admin/*; leave unset to disable
# TRUST_KEY=long-random-string           # signs product graphs (HMAC-SHA256); falls back to ADMIN_TOKEN, then a public dev key
```

Frontend (`frontend/.env`, optional): `VITE_API_BASE` and `VITE_BASE_URI` (must equal `BASE_URI`).

> **Never commit `.env`** — it is in `.gitignore` by default.

---

## Evaluation

Run it yourself (needs the local catalogue and the cached model):

```bash
cd backend
python -m eval.run_eval      # writes eval/RESULTS.md and eval/results.json
pytest                       # includes regression guards on these numbers
```

30 labelled queries in three classes, plus 3 queries with no right answer
(`backend/eval/queries.json`). Semantic search uses the production relevance floor.

| Query class | Method | Recall@5 | MRR | Hit@1 |
|---|---|---|---|---|
| exact (10) | keyword | 1.00 | 1.00 | 1.00 |
|  | semantic | 1.00 | 1.00 | 1.00 |
| paraphrase (10) | keyword | 0.00 | 0.00 | 0.00 |
|  | semantic | 1.00 | 0.95 | 0.90 |
| vague (10) | keyword | 0.05 | 0.10 | 0.10 |
|  | semantic | 0.73 | 0.73 | 0.60 |
| **overall (30)** | keyword | 0.35 | 0.37 | 0.37 |
|  | **semantic** | **0.91** | **0.89** | **0.83** |

What it shows, including the unflattering parts:

- Meaning wins exactly where the plan predicted: paraphrased and vague queries, where keyword
  search finds almost nothing.
- On exact lookups (names, brands, a model number) the two **tie**. On a 72-product catalogue
  there is no room for semantic search to lose; a larger catalogue could differ.
- Semantic search still misses some vague queries (`make music at home` finds the turntable,
  not the studio monitors; `gear for a camping trip` finds 1 of 5). The full list is in
  `eval/RESULTS.md`.
- Fusing the two rankings (reciprocal rank fusion) gave **no gain**, so it is not in the API.
- All three off-topic queries correctly return nothing.
- Relevance labels were drafted from the catalogue text and are a first pass, not ground truth.
  With 30 queries these numbers show direction, not precision.

### Is the RDF valid?

`frontend/src/rdf.js` is run under Node over all 72 products and its Turtle, RDF/XML and JSON-LD
are parsed by **rdflib**, an independent implementation (`backend/tests/test_rdf_interop.py`):

- all three syntaxes parse;
- all three are isomorphic, i.e. they describe the same graph;
- that graph equals the one the Python service (`rdf_service.py`) builds from the same rows.

This check found that the JSON-LD output used to drop `dcterms:created`, category types and
language tags and left numbers untyped. It was fixed, and the test now guards it.

---

## Reading

1. Thomas B. Passin, *Explorer's Guide to the Semantic Web*, Manning, 2004.
2. Daconta, Obrst & Smith, *The Semantic Web: A Guide to the Future of XML, Web Services, and
   Knowledge Management*, Wiley, 2003.
3. Antoniou & van Harmelen, *A Semantic Web Primer*, MIT Press, 2004.
4. [www.semanticweb.org](http://www.semanticweb.org)

---

## Licence

MIT.
