# AI Semantic E-Commerce Search — Implementation Plan

## 1. Project Overview

Traditional e-commerce search engines rely on **keyword matching** — they compare the literal words in a search query against the literal words in product titles and descriptions. This approach fails often: a search for "warm winter jacket for men" may completely miss a product titled "insulated men's parka," even though the two mean almost the same thing, because the words don't overlap.

**Semantic search** solves this by understanding *meaning* rather than exact words. It works by converting both product data and user queries into **embeddings** — numerical vectors that represent meaning in a high-dimensional space. Two pieces of text that mean similar things end up close together in this space, even if they share no common words. The system then retrieves products by measuring the similarity between the query vector and product vectors, rather than by string matching.

In short, this project is a search engine for a product catalog that:
1. Converts every product's text (name, description, category, brand) into a vector embedding.
2. Converts the user's search query into a vector embedding using the same model.
3. Finds and ranks products whose embeddings are closest (most semantically similar) to the query embedding.
4. Combines this with traditional filters (price, category, brand) to give practical, usable results.

---

## 2. Requirements

### 2.1 Functional Requirements

| ID | Requirement |
|----|-------------|
| FR1 | Users can search using natural language queries (e.g., "comfortable running shoes for flat feet") |
| FR2 | System returns semantically relevant products, ranked by relevance score |
| FR3 | Users can filter results by category, price range, brand, and rating |
| FR4 | System supports autocomplete / query suggestions while typing |
| FR5 | Admins can add, update, or delete products; embeddings regenerate automatically on change |
| FR6 | System falls back to keyword search if the embedding/vector service is unavailable |
| FR7 | (Optional) "Find similar products" feature based on a selected product's embedding |
| FR8 | (Optional) Personalized ranking based on a user's past search/click history |

### 2.2 Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR1 | Search latency should stay under ~500ms for a typical query |
| NFR2 | System should scale to a catalog of at least tens of thousands of products without major redesign |
| NFR3 | Semantic matching should be reasonably accurate (validated via evaluation, see Section 6) |
| NFR4 | System should degrade gracefully — no hard failure if AI components go down |
| NFR5 | Codebase should be modular so the embedding model or vector DB can be swapped later |

---

## 3. Technology Stack

| Layer | Technology | Reasoning |
|-------|------------|-----------|
| Frontend | React (Vite) | Fast dev experience, component-based UI, good fit for dynamic search results |
| Backend API | FastAPI (Python) | Native compatibility with ML/embedding libraries; async support for low latency |
| Embedding Model | Sentence-Transformers (`all-MiniLM-L6-v2`) | Free, runs locally, no API cost, good semantic accuracy for its size (384 dimensions) |
| Vector Storage | PostgreSQL + `pgvector` extension | Keeps structured and vector data in one database; simpler than running a separate vector DB; supports cosine similarity search with indexing |
| Primary Database | PostgreSQL | Reliable relational store for products, users, categories, logs |
| Caching | Redis | Caches frequent/repeated queries to reduce latency and load |
| Containerization | Docker + docker-compose | Reproducible environment, easy to run all services together |

**Why pgvector instead of a dedicated vector database (Pinecone/Weaviate/Qdrant):**
Using pgvector keeps the entire system in a single database, avoiding the complexity of syncing two separate data stores. It is sufficient for catalogs up to a few hundred thousand products and is the most practical choice for a project of this scope. A dedicated vector DB can be swapped in later if scale demands it, since the vector logic is isolated to one service layer.

---

## 4. System Architecture

```
┌─────────────┐        ┌──────────────┐        ┌────────────────────┐
│   Frontend   │──────▶│  Backend API  │──────▶│  Embedding Service  │
│ (React)      │        │  (FastAPI)    │        │ (Sentence-BERT)     │
└─────────────┘        └──────┬───────┘        └─────────┬──────────┘
                               │                            │
                               ▼                            ▼
                    ┌─────────────────┐         ┌────────────────────┐
                    │  PostgreSQL DB   │◀───────▶│  pgvector column    │
                    │ (product details)│         │ (product_embeddings)│
                    └─────────────────┘         └────────────────────┘
                               │
                               ▼
                        ┌─────────────┐
                        │   Redis      │  (query result cache)
                        └─────────────┘
```

### 4.1 Data Flow — Ingestion (offline/batch)
1. A product is created or updated in the `products` table.
2. Its text fields (name, description, category, brand) are concatenated into one text blob.
3. The embedding service encodes this text into a 384-dimension vector.
4. The vector is stored in `product_embeddings`, linked to the product by `product_id`.

### 4.2 Data Flow — Query Time
1. User submits a search query from the frontend.
2. Backend encodes the query into a vector using the same embedding model.
3. Backend runs a similarity search (cosine similarity via pgvector's `<=>` operator) against `product_embeddings`, retrieving the top-N closest products.
4. Backend joins these results with the `products` table for full details.
5. Any active filters (price, category, brand) are applied.
6. Results are ranked and returned as JSON to the frontend.
7. (Optional) A hybrid score combines semantic similarity with a traditional keyword match score for better precision on exact-match queries (e.g., brand names, model numbers).

---

## 5. Database Schema

### 5.1 `products`
| Column | Type | Notes |
|--------|------|-------|
| product_id | UUID / SERIAL (PK) | |
| name | TEXT | |
| description | TEXT | |
| category_id | INT (FK → categories) | |
| brand | VARCHAR | |
| price | DECIMAL | |
| stock_quantity | INT | |
| rating_avg | FLOAT | |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

### 5.2 `categories`
| Column | Type |
|--------|------|
| category_id | SERIAL (PK) |
| name | VARCHAR |
| parent_category_id | INT (self-referencing, nullable) |

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
Used for analytics and for the evaluation phase.
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
| product_id | FK → products | |
| embedding | VECTOR(384) | Dimension depends on model; 384 for MiniLM |
| model_version | VARCHAR | Tracks which embedding model generated the vector, useful if the model is upgraded later |

---

## 6. Implementation Plan (by Phase)

### Phase 0 — Environment & Project Setup
**Goal:** A running skeleton of the system, with no features yet.
- Select a public product dataset (e.g., a Kaggle Amazon/Flipkart product dataset).
- Set up the repository structure separating backend, frontend, embedding scripts, and database migrations.
- Install and configure PostgreSQL with the `pgvector` extension enabled.
- Set up the Python backend environment with FastAPI and the required libraries.
- Scaffold the React frontend project.

**Outcome:** Backend and frontend both run locally and can talk to a working database.

---

### Phase 1 — Database Design & Data Loading
**Goal:** Real product data available in the database in a clean, queryable form.
- Write and run migration scripts for all tables described in Section 5.
- Enable the `vector` extension in PostgreSQL.
- Write an ETL script to clean the source dataset and bulk-load it into `products` and `categories`.
- Add indexes on commonly filtered columns (`category_id`, `price`, `brand`).

**Outcome:** The database is populated with real, clean product data that can be queried with plain SQL.

---

### Phase 2 — Embedding Pipeline
**Goal:** Every product in the catalog has a semantic vector representation.
- Load the `all-MiniLM-L6-v2` embedding model.
- Write a script that concatenates each product's relevant text fields and encodes them in batches.
- Insert the resulting vectors into `product_embeddings`.
- Create a similarity index (e.g., `ivfflat` with cosine distance) on the embedding column to keep lookups fast as the catalog grows.
- Validate manually: pick a sample query, compute its embedding, run a raw similarity query, and confirm the top results make semantic sense.

**Outcome:** The entire product catalog is represented as vectors, with a verified similarity query working directly in SQL.

---

### Phase 3 — Search API
**Goal:** A backend endpoint that performs true semantic search.
- Build a `/search` endpoint that accepts a query string plus optional filters (category, price range, brand).
- Endpoint logic: encode the query → retrieve nearest-neighbor products from `product_embeddings` → join with `products` for full details → apply filters → return ranked, paginated results.
- Build a `/search/keyword` fallback endpoint using plain SQL text matching, used both as a comparison baseline and as a fail-safe if the embedding service is unavailable.
- (Optional) Implement hybrid scoring that blends semantic similarity with keyword match strength, improving results for queries that include exact brand names or model numbers.
- Build a lightweight `/autocomplete` endpoint for query suggestions.

**Outcome:** A working, testable search API returning semantically ranked products.

---

### Phase 4 — Frontend
**Goal:** A usable interface for end users to interact with the search system.
- Build a debounced search bar (avoids firing a request on every keystroke).
- Build a results grid showing product image, name, price, and rating.
- Build a filter sidebar (category, price range, brand).
- Add loading and empty/no-results states.
- (Optional) Add a side-by-side toggle comparing semantic search results against keyword search results — useful for demonstrating the project's value.

**Outcome:** A complete, working end-to-end demo — a user can type a natural-language query and see relevant results.

---

### Phase 5 — Performance & Reliability
**Goal:** Make the system fast, resilient, and deployable.
- Add Redis caching for repeated/frequent search queries.
- Log every search to `search_logs` for analytics and evaluation.
- Add basic error handling: empty queries, database downtime, and embedding-model failures should all fall back gracefully rather than crash.
- Containerize the full stack (backend, frontend, database) with Docker and docker-compose.

**Outcome:** A resilient, dockerized application that can be started with a single command.

---

### Phase 6 — Evaluation
**Goal:** Quantifiable proof that semantic search outperforms keyword search on natural-language queries.
- Prepare a set of test queries covering exact matches, paraphrased queries, and vague/descriptive queries.
- Run each test query through both the semantic and keyword endpoints.
- Manually label top results as relevant/not relevant and compute a simple metric such as Precision@5 for each approach.
- Summarize findings in a comparison table, highlighting where semantic search wins (primarily on paraphrased and descriptive queries).

**Outcome:** Documented, evidence-based comparison showing the practical benefit of the semantic approach.

---

## 7. Stretch Goals (Optional Enhancements)

| Feature | Description |
|---------|-------------|
| Image-based similarity search | Use a model like CLIP to embed product images, enabling "find visually similar products" |
| Personalized ranking | Use `search_logs` click history to bias ranking toward a user's preferences |
| Multilingual search | Swap in a multilingual embedding model to support non-English queries |
| Typo tolerance | Add fuzzy matching as a fallback layer for misspelled queries |
| LLM query expansion | Use an LLM to rewrite vague queries into more descriptive text before embedding, improving retrieval quality |

---

## 8. Summary

This project demonstrates how combining a relational database with vector embeddings and similarity search can meaningfully improve e-commerce product discovery. The plan is structured so that each phase produces a working, testable component: first the data layer, then the embedding pipeline, then the search API, then the interface, and finally performance hardening and a data-backed evaluation. This incremental structure keeps the project functional at every stage rather than requiring everything to come together only at the very end.
