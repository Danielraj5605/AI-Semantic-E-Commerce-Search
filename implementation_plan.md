# CatalogueGraph — Implementation Plan

**21CSE452T · Semantic Web** — Professional Elective, School of Computing
*A product catalogue published as RDF, retrieved by meaning.*

---

## 1. Project Overview

Traditional e-commerce search relies on **keyword matching** — comparing the literal words of a query
against the literal words of a product title. It fails often: "warm winter jacket for men" misses a
product titled "insulated men's parka" entirely, because the words do not overlap even though the
meanings almost coincide.

Two different traditions answer that problem, and this project builds both and puts them next to each
other:

**Statistical semantics.** Convert product text and query text into **embeddings** — vectors that
place similar meanings close together in a high-dimensional space — and retrieve by distance. This is
what `sentence-transformers` does. It is powerful, approximate, and entirely opaque: the model cannot
tell you *why* two things are close.

**Formal semantics.** Publish the catalogue as **RDF** over shared vocabularies, so every product has
a URI, is typed against an ontology, describes itself in terms other systems already understand, and
carries provenance for its claims. This is the Semantic Web proper — the subject of this course. It is
precise, inspectable, and says nothing at all about whether "parka" is like "jacket" unless somebody
asserted it.

> **The thesis of this project.** The two are complementary, not competing. The graph supplies
> identity, structure, vocabulary and provenance; the vector service supplies the similarity judgment
> that no ontology contains. Treating retrieval as a **service invocation** (Unit 3) whose result the
> graph *records* — rather than pretending the model is doing inference — keeps both honest. The
> interface is built to make that distinction visible on every screen.

Concretely, the system:

1. Stores the catalogue relationally in PostgreSQL.
2. Encodes every product's text into a 384-dimension vector, stored alongside it via `pgvector`.
3. Encodes the user's query with the same model and retrieves the nearest products.
4. **Lifts every row and result into RDF at render time** — URIs, `rdf:type`, schema.org properties,
   typed literals, provenance — and serialises it as Turtle, RDF/XML or JSON-LD on demand.
5. Presents each result with a stated **degree of belief** and a **proof trace**, rather than an
   unexplained score.

---

## 2. Requirements

### 2.1 Functional — retrieval

| ID | Requirement |
|----|-------------|
| FR1 | Users can search using natural-language queries ("comfortable running shoes for flat feet") |
| FR2 | System returns semantically relevant products, ranked by relevance score |
| FR3 | Users can filter by category, price range, brand and rating |
| FR4 | System supports autocomplete / query suggestions while typing |
| FR5 | Admins can add, update or delete products; embeddings regenerate on change |
| FR6 | System falls back to keyword search if the embedding service is unavailable |
| FR7 | *(Optional)* "Find similar products" from a selected product's embedding |
| FR8 | *(Optional)* Personalised ranking from a user's search/click history |

### 2.2 Functional — semantic publication

| ID | Requirement | Unit |
|----|-------------|------|
| FR9 | Every product, brand and category is identified by a dereferenceable URI | 1 |
| FR10 | Catalogue rows are mapped to RDF triples over reused vocabularies (schema.org, DC, PROV-O) — no invented term where a standard one exists | 1, 4 |
| FR11 | Categories are published as an `owl:Class` hierarchy linked by `rdfs:subClassOf`, and are browsable as an ontology | 2 |
| FR12 | The result graph is serialisable to Turtle, RDF/XML and JSON-LD, and the output must actually parse | 5 |
| FR13 | The equivalent SPARQL query is displayed for whatever the user asked through the UI | 5 |
| FR14 | Result pages embed JSON-LD in the document head, so the page is machine-readable to crawlers | 1, 5 |
| FR15 | The retrieval step is described as an invoked service, with its binding and method stated | 3 |
| FR16 | Every result carries provenance (`prov:wasDerivedFrom`) and an explicit degree of belief | 3 |
| FR17 | Every result can produce a proof trace — the ordered steps that caused it to be returned | 1 |
| FR18 | The interface distinguishes what is **asserted** from what is **believed**, and never presents a similarity score as a fact about the product | 1, 3 |

### 2.3 Non-functional

| ID | Requirement |
|----|-------------|
| NFR1 | Search latency under ~500 ms for a typical query |
| NFR2 | Scales to tens of thousands of products without redesign |
| NFR3 | Semantic matching validated by evaluation (Section 8) |
| NFR4 | Degrades gracefully — no hard failure if AI components go down |
| NFR5 | Modular enough that the embedding model or vector store can be swapped |
| NFR6 | The RDF view is derived, never stored — it cannot drift from the relational source |
| NFR7 | UI is theme-aware (light/dark), keyboard-navigable, and legible at 400 px width |

---

## 3. Technology Stack

| Layer | Technology | Reasoning |
|-------|------------|-----------|
| Frontend | React 19 (Vite) | Component model suits the result/inspector/rail split; no CSS framework, so the design system stays small and owned |
| RDF layer | Hand-written (`src/rdf.js`) | ~450 lines. A library would hide precisely the machinery the course is about; writing the serialisers is the exercise |
| Vocabularies | schema.org, RDF/RDFS, OWL, XSD, DC Terms, FOAF, PROV-O | Unit 4 is explicit that reusing existing ontologies beats authoring new ones. Only `cat:` and `ex:` are local |
| Backend API | FastAPI (Python) | Native compatibility with the embedding libraries; async for low latency |
| Embedding model | `all-MiniLM-L6-v2` | Free, local, no API cost, good accuracy for 384 dimensions |
| Vector storage | PostgreSQL + `pgvector` | Structured and vector data in one store; cosine similarity with indexing |
| Primary database | PostgreSQL | Relational store for products, categories, users, logs |
| Caching | TTL cache (in-memory), Redis at scale | Avoids re-encoding repeated queries |
| Containerisation | Docker + docker-compose | Reproducible; one command to start everything |

**Why pgvector rather than Pinecone/Weaviate/Qdrant.** Keeping everything in one database avoids
syncing two stores, and is sufficient to a few hundred thousand products. Because the vector logic is
isolated to one service layer, a dedicated vector DB can replace it later without touching the rest.

**Why no triple store.** The same argument, applied to RDF. Materialising the graph into a separate
store would create a second copy to keep consistent, for no benefit at this scale. Instead the graph
is a **view**, computed from the rows on demand — which is the direct-mapping approach of Unit 4, and
satisfies NFR6 by construction.

---

## 4. System Architecture

```
┌──────────────┐        ┌───────────────┐        ┌─────────────────────┐
│   Frontend   │──────▶│  Backend API  │──────▶│  Embedding Service  │
│   (React)    │        │   (FastAPI)   │        │   (Sentence-BERT)   │
│              │        └───────┬───────┘        └──────────┬──────────┘
│  rdf.js      │                │                            │
│  row → RDF   │                ▼                            ▼
│  → Turtle    │      ┌──────────────────┐        ┌────────────────────┐
│  → RDF/XML   │      │   PostgreSQL     │◀──────▶│ pgvector column    │
│  → JSON-LD   │      │ (product detail) │        │(product_embeddings)│
│  → SPARQL    │      └──────────────────┘        └────────────────────┘
└──────────────┘                │
                                ▼
                         ┌─────────────┐
                         │    Redis    │  (query result cache)
                         └─────────────┘
```

The RDF transformation lives **client-side**, in the same process that renders the result. That is a
deliberate choice: it demonstrates that publishing a graph is a matter of applying mapping rules to
rows, not of adopting new infrastructure.

### 4.1 Data flow — ingestion (offline/batch)

1. A product is created or updated in `products`.
2. Its text fields (name, description, category, brand) are concatenated into one blob.
3. The embedding service encodes the blob into a 384-dimension vector.
4. The vector is stored in `product_embeddings`, keyed by `product_id`.

### 4.2 Data flow — query time

1. The user submits a natural-language query.
2. The backend encodes it into a vector with the same model.
3. pgvector's `<=>` operator finds the top-N nearest `product_embeddings`.
4. Results are joined back to `products` for full detail.
5. Class and literal constraints are applied.
6. Ranked results return as JSON.
7. **The frontend lifts each result into RDF**, attaches a belief band and a proof trace, and embeds
   the result set as JSON-LD in the document head.

---

## 5. Database Schema

### 5.1 `products`
| Column | Type | Notes |
|--------|------|-------|
| product_id | UUID (PK) | Becomes the RDF subject URI |
| name | TEXT | |
| description | TEXT | |
| category_id | INT (FK → categories) | Resolves to an `owl:Class` |
| brand | VARCHAR | Lifted to its own `schema:Brand` resource |
| price | DECIMAL | |
| stock_quantity | INT | |
| rating_avg | FLOAT | |
| created_at / updated_at | TIMESTAMP | |

### 5.2 `categories`
| Column | Type | Notes |
|--------|------|-------|
| category_id | SERIAL (PK) | |
| name | VARCHAR | Becomes the class local name |
| parent_category_id | INT (self-ref, nullable) | Becomes `rdfs:subClassOf` |

### 5.3 `product_images`
| Column | Type |
|--------|------|
| image_id | SERIAL (PK) |
| product_id | FK → products |
| image_url | TEXT |

### 5.4 `users`
| Column | Type |
|--------|------|
| user_id | UUID (PK) |
| name | VARCHAR |
| email | VARCHAR (unique) |
| password_hash | TEXT |

### 5.5 `search_logs`
| Column | Type |
|--------|------|
| log_id | SERIAL (PK) |
| user_id | FK → users (nullable) |
| query_text | TEXT |
| clicked_product_id | FK → products (nullable) |
| timestamp | TIMESTAMP |

### 5.6 `product_embeddings`
| Column | Type | Notes |
|--------|------|-------|
| product_id | FK → products (PK) | |
| embedding | VECTOR(384) | Dimension follows the model |
| model_version | VARCHAR | Tracks which model produced the vector |

---

## 6. The Semantic Layer

### 6.1 Namespaces (Unit 5)

| Prefix | Namespace | Why it is here |
|---|---|---|
| `rdf:` | `http://www.w3.org/1999/02/22-rdf-syntax-ns#` | `rdf:type` asserts class membership |
| `rdfs:` | `http://www.w3.org/2000/01/rdf-schema#` | `rdfs:subClassOf` builds the taxonomy |
| `owl:` | `http://www.w3.org/2002/07/owl#` | Class and property declarations |
| `xsd:` | `http://www.w3.org/2001/XMLSchema#` | Typed literals for price, rating, dates |
| `schema:` | `http://schema.org/` | The de-facto shared e-commerce vocabulary |
| `dcterms:` | `http://purl.org/dc/terms/` | Descriptive and provenance metadata |
| `foaf:` | `http://xmlns.com/foaf/0.1/` | Agents and people (Unit 5 case study) |
| `prov:` | `http://www.w3.org/ns/prov#` | Where each assertion came from |
| `cat:` | `http://example.org/ontology/catalog#` | **Local** — catalogue classes and properties |
| `ex:` | `http://example.org/catalog/` | **Local** — one URI per catalogue resource |

Eight of ten are reused. That ratio is the point of Unit 4's "Reusing Existing Ontologies".

### 6.2 Direct mapping rules (Unit 4)

| Column | Predicate | Treatment |
|---|---|---|
| `products.product_id` | *(subject)* | Primary key becomes `ex:product/{uuid}` |
| `products.name` | `schema:name` | Plain literal, `@en` |
| `products.description` | `schema:description` | Plain literal, `@en` |
| `products.brand` | `schema:brand` | Lifted into its own `schema:Brand` resource |
| `products.category_id` | `schema:category` / `rdf:type` | FK resolved to an `owl:Class` |
| `products.price` | `schema:offers` → `schema:price` | Reified as a `schema:Offer` node; `xsd:decimal` |
| `products.stock_quantity` | `schema:offers` → `schema:availability` | `schema:InStock` / `schema:OutOfStock` |
| `products.rating_avg` | `schema:aggregateRating` | Blank node of type `schema:AggregateRating` |
| `products.image_url` | `schema:image` | Object is a URI reference, not a string |
| `products.created_at` | `dcterms:created` | `xsd:dateTime` |
| *(query result)* | `cat:similarityScore` | Query-scoped annotation, `xsd:double` |

Two rules deserve comment. **Price and rating are reified** rather than attached as bare literals,
because a price is a fact about an *offer* and a rating is a fact about an *aggregate*, not about the
product itself — collapsing them would assert something false. And **`cat:similarityScore` is
query-scoped**: it is only true relative to the query that produced it, which is why it is annotated
rather than stored.

### 6.3 The local ontology (Unit 2)

```
cat:CatalogueThing        a owl:Class .
schema:Product            rdfs:subClassOf cat:CatalogueThing .
cat:{Category}            a owl:Class ;
                          rdfs:subClassOf cat:{ParentCategory} | cat:CatalogueThing .
cat:similarityScore       a owl:DatatypeProperty ; rdfs:range xsd:double .
schema:brand              a owl:ObjectProperty   ; rdfs:range schema:Brand .
```

Deliberately shallow — a terminology plus subsumption, which is the level most working vocabularies
actually sit at ("Ontologies Today", Unit 2). Nothing is asserted that the source data does not
support.

### 6.4 Serialisation (Unit 5)

Three concrete syntaxes over the same graph, generated live from the current result set:

- **Turtle** — `@prefix` header limited to prefixes the graph actually uses; QNames that are not
  legal `PN_LOCAL` (a UUID path contains `/`) are written as full IRIs so the output genuinely parses.
- **RDF/XML** — `rdf:Description` per subject, `rdf:nodeID` for blank nodes, `rdf:datatype` and
  `xml:lang` attributes on typed and tagged literals.
- **JSON-LD** — built structurally rather than from the flat triple list, so the tree shape survives.
  This is the form embedded in the document head.

### 6.5 Query (Unit 5)

The interface renders the **equivalent SPARQL** for whatever it was asked. Class selections become
graph patterns; price and rating bounds become `FILTER` clauses; and the similarity step appears as a
`SERVICE` block — which is the honest rendering, since no triple store computes cosine distance.

### 6.6 Trust, belief and proof (Units 1, 3)

A similarity score is not a truth value, and the UI refuses to present it as one:

| Band | Condition | Meaning |
|---|---|---|
| Asserted | keyword mode | Literal match — certain, but blind to meaning |
| Strong belief | score ≥ 0.65 | Query and product vectors closely aligned |
| Moderate belief | 0.45 ≤ score < 0.65 | Related, but the match is not tight |
| Weak belief | score < 0.45 | Distant — a peripheral suggestion |

Each result also yields a **proof trace**: query lifted → service invoked → similarity computed →
class entailed → provenance recorded. This is as far up the proof layer as an embedding-based system
can honestly climb, and the UI labels it as partial.

---

## 7. Implementation Plan (by Phase)

### Phase 0 — Environment & Project Setup
**Goal:** a running skeleton, no features.
- Select a public product dataset (Kaggle Amazon/Flipkart).
- Repository structure separating backend, frontend, scripts, migrations.
- PostgreSQL with `pgvector` enabled.
- FastAPI backend environment; React frontend scaffold.

**Outcome:** both tiers run locally and reach the database.

---

### Phase 1 — Database Design & Data Loading
**Goal:** clean, queryable product data.
- Migration scripts for every table in Section 5; enable the `vector` extension.
- ETL to clean the source dataset and bulk-load `products` and `categories`.
- Indexes on `category_id`, `price`, `brand`, `rating_avg`.
- **Ensure `categories.parent_category_id` is genuinely populated** — the class hierarchy of Phase 3
  is only as deep as this column allows.

**Outcome:** real data, queryable with plain SQL.

---

### Phase 2 — Embedding Pipeline
**Goal:** every product has a vector.
- Load `all-MiniLM-L6-v2`; concatenate each product's text fields; encode in batches.
- Insert vectors into `product_embeddings` with `model_version` recorded.
- Create an `ivfflat` cosine index on the embedding column.
- Validate manually: embed a sample query, run the raw similarity SQL, confirm the top results make
  sense.

**Outcome:** the catalogue is represented as vectors, verified directly in SQL.

---

### Phase 3 — Search API
**Goal:** a backend endpoint doing true semantic search.
- `/api/search` — query string plus optional filters; encode → nearest neighbours → join → filter →
  ranked, paginated results.
- `/api/search/keyword` — SQL text matching, as both comparison baseline and fail-safe (FR6).
- `/api/filters` — categories with their parent links, brands, price range. This endpoint is the raw
  material the frontend turns into a class hierarchy, so the parent links matter.
- `/api/autocomplete` — prefix suggestions.
- *(Optional)* hybrid scoring blending semantic similarity with keyword match strength, for queries
  containing exact brand names or model numbers.

**Outcome:** a working, testable search API.

---

### Phase 4 — Semantic Publication Layer ★
**Goal:** the catalogue is a graph, not just a result list. *(FR9–FR14)*
- Implement `src/rdf.js`: namespace table, term constructors, `productToTriples`, `resultsToTriples`.
- Implement the three serialisers, and **verify each parses** — legal Turtle QNames, correct
  `rdf:nodeID` handling, parseable JSON-LD.
- Build the class tree and axiom list from the flat category list.
- Implement `buildSPARQL` so every UI constraint has a visible query counterpart.
- Embed the result set as JSON-LD in the document head; add Dublin Core metadata and a
  `WebApplication` description to `index.html`.

**Outcome:** every answer can be exported as valid RDF in three syntaxes, and the page is
machine-readable.

---

### Phase 5 — Interface
**Goal:** an interface that teaches the model it is built on. *(FR11, FR15–FR18)*
- Design system: paper/ink ground, serif display, monospace for every formal term, and **colour as a
  type system** — teal resources, indigo classes, amber literals, violet blank nodes, slate
  predicates — applied identically in tables, graph nodes and code panes.
- Debounced search bar, framed as binding `?query`.
- **Ontology rail** instead of a filter sidebar: the class tree *is* the category filter.
- **Resource cards** announced by URI, expanding into triples / graph / proof.
- **RDF visualisation** in inline SVG: a property star per resource, and a class-clustered view of
  the whole answer set with node size encoding similarity.
- **Inspector drawer**: Turtle · RDF/XML · JSON-LD · SPARQL · Mapping · Axioms · Prefixes.
- **Concepts drawer**: the layer cake with honest per-layer status, and the syllabus map.
- Meaning/Strings toggle for the side-by-side comparison the evaluation needs.
- Loading, empty and error states; light/dark themes; responsive to 400 px.

**Outcome:** a complete end-to-end demo in which the Semantic Web concepts are visible, not implied.

---

### Phase 6 — Performance & Reliability
**Goal:** fast, resilient, deployable.
- Redis caching for repeated queries.
- Log every search to `search_logs`.
- Error handling: empty queries, database downtime and embedding-model failure all degrade rather
  than crash — the UI explicitly offers Strings mode when the encoder is unreachable.
- Containerise backend, frontend and database with docker-compose.

**Outcome:** a resilient, dockerised application started with one command.

---

### Phase 7 — Evaluation
**Goal:** evidence, not assertion.
- Test queries in three classes: exact matches, paraphrases, and vague/descriptive queries.
- Run each through both the semantic and keyword endpoints.
- Label top results relevant/not relevant; compute Precision@5 for each approach.
- Summarise in a comparison table, showing where semantic search wins — expected to be on
  paraphrased and descriptive queries, and *not* on exact brand or model-number lookups, which is
  worth reporting rather than hiding.
- **Also validate the graph**: run the generated Turtle and RDF/XML through an external parser
  (`rapper`, Apache Jena `riot`, or the W3C RDF validator) and the JSON-LD through the JSON-LD
  playground. A graph that does not parse is not published.

**Outcome:** a documented, evidence-based comparison, plus proof that the RDF output is valid.

---

## 8. Stretch Goals

| Feature | Description | Unit |
|---------|-------------|------|
| SPARQL endpoint | Materialise the graph into Apache Jena Fuseki and make the displayed query actually executable | 5 |
| Content negotiation | Serve `text/turtle` / `application/rdf+xml` from `/api/product/{id}` by `Accept` header — real Linked Data publishing | 1, 4 |
| Ontology mapping | Map the local `cat:` classes onto a second vocabulary (GoodRelations, Product Types) with `owl:equivalentClass` | 2, 4 |
| FOAF user profiles | Publish user accounts as FOAF, and link `search_logs` to them for a provenance-aware history | 5 |
| Agent negotiation | A second agent that consumes the JSON-LD and re-ranks — Unit 3's intelligent agents, made concrete | 3 |
| Image similarity | CLIP embeddings for "visually similar products" | — |
| Multilingual search | A multilingual embedding model; the `@en` language tags already anticipate this | — |
| LLM query expansion | Rewrite vague queries into descriptive text before embedding | — |

---

## 9. Summary

The project demonstrates two things at once. The first is practical: combining a relational database
with vector embeddings measurably improves product discovery for natural-language queries, and the
evaluation phase is designed to prove it with numbers rather than assert it.

The second is the course's own subject. The same catalogue, published as RDF over reused
vocabularies, becomes something other systems can consume without prior agreement — that is what the
layer cake is for, and each of its layers has a visible counterpart in the interface. Where the
system reaches a layer it cannot honestly implement, it says so.

Each phase produces a working, testable component: the data layer, then the embeddings, then the API,
then the graph, then the interface, then hardening and evaluation. The system is functional at every
stage rather than only at the end.

---

## 10. Status and deviations from this plan

Written after the build, so the plan above can be read against what actually exists.

| Phase | Status | Notes |
|---|---|---|
| 0 Setup · 1 Data · 2 Embeddings · 3 Search API | Done | Local SQLite mode added alongside Neon/pgvector |
| 4 Semantic publication | Done | Turtle, RDF/XML and JSON-LD all validated by an independent parser (rdflib) and equal the Python mapping |
| 5 Interface | Done | |
| 6 Performance & reliability | Done, one item deferred | In-memory TTL cache instead of Redis (single process, so Redis adds nothing yet). Degradation, logging and `/health` implemented and tested. Docker files written but **not built** on the author's machine |
| 7 Evaluation | Done | `backend/eval/`; results in the README. Labels are a first pass |

| Requirement | Status |
|---|---|
| FR1-FR4, FR6 | Done |
| FR5 admin CRUD | Done; off unless `ADMIN_TOKEN` is set |
| FR7 find similar | Done |
| FR8 personalised ranking | **Partly done.** Clicks are logged (`POST /api/click`) and can re-rank results by global click popularity (`CLICK_BOOST_WEIGHT`, off by default). It is *not* per-user: the app has no accounts, so there is no one to personalise for. Not evaluated, since the labelled queries have no click history |
| FR9 dereferenceable URIs | Done when `BASE_URI` points at the API; the default stays `example.org` |
| FR10-FR18 | Done (Logic, Proof and Trust layers remain partial, and are labelled so) |

**Changes made while building, and why**

- **Category hierarchy.** The data had no parent categories, so the class tree was flat. Added
  `set_category_hierarchy.py` and made category filtering include subclasses.
- **Keyword search tokenises.** Whole-phrase `ILIKE` matched almost nothing for multi-word queries,
  which made both the fallback and the evaluation baseline unfair.
- **Fallback narrowed.** Only a missing encoder falls back to keyword; a database failure is a 503.
- **Hybrid ranking evaluated, not shipped.** Reciprocal rank fusion gave no gain over semantic.
- **JSON-LD fixed.** It had silently lost dates, category types, language tags and datatypes.

**Known limits**

- 72 products and 30 queries: the evaluation shows direction, not precision.
- On exact lookups semantic and keyword tie; this may change on a larger catalogue.
- Vague queries are the weak spot (e.g. "make music at home").
- The Neon/pgvector path was not exercised in this round (Neon was unreachable); the SQLite path was.
