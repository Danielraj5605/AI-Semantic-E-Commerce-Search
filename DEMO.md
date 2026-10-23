# Demo script

About 8 minutes. Each step names the syllabus unit it shows. Start the backend and frontend (see
README), open http://localhost:5173, and have `backend/eval/RESULTS.md` ready.

## 0. The thesis (30 s)
> Statistical semantics (embeddings) and formal semantics (RDF) answer different questions. This
> app puts them side by side and says which is which.

## 1. Meaning beats strings: *Unit 3, agents and services*
1. Search **`headphones that cancel outside sound`** in **Meaning** mode. The headphones come first.
2. Flip the toggle to **Strings**. Nothing is found: no word overlaps.
3. Point at the **service descriptor** and the **belief** label on each card: the score is a
   *degree of belief*, not a fact about the product.

## 2. Every result is a resource: *Unit 1, RDF*
1. Note the card is announced by its **URI**, not its name.
2. Expand **Triples**, then **Graph**: the same description as a table and as a node-link picture.
3. Expand **Why this?**: the proof trace, with the *measured* precision at that score.
4. Expand **Reasoning**: the facts the reasoner derived (a laptop is *Electronics*; this one is *Premium* because
   899.99 ≥ 200). Open one to see its proof tree, grounded in a catalogue row and an ontology axiom.
5. In the same panel click **Verify this graph**, then **Change the price to $0.01 and verify**: one altered triple
   breaks the signature. Open **Inspect → Logic** to show the ontology, the rules and the whole-catalogue conformance check.

## 3. The class tree is the filter: *Unit 2, ontologies*
1. In the left rail click **Electronics**. Laptops, smartphones and audio all appear.
2. Say: *this is `rdfs:subClassOf` entailment. A laptop is an Electronics, so it is returned.*
3. Open **Axioms** in the Inspector to show the `owl:Class` / `rdfs:subClassOf` statements.

## 4. Same graph, three syntaxes: *Unit 5, XML and serialisation*
1. **Inspect graph**: flip Turtle -> RDF/XML -> JSON-LD.
2. Say: *an independent parser (rdflib) reads all three and agrees they are the same graph; that
   is a test in the repo, not a claim.*
3. Open the **SPARQL** tab: the query equivalent to what was just asked, with the similarity step
   shown honestly as a `SERVICE` block.

## 5. Exposing a relational database: *Unit 4, ontology engineering*
1. **Mapping** tab: the column-by-column rules that turn a SQL row into triples.
2. Point out that price is a `schema:Offer` and rating a `schema:AggregateRating`: they are facts
   about an offer and an aggregate, not about the product.
3. Optional, if the API runs with `BASE_URI=http://localhost:8000/api/`:
   `curl -H "Accept: text/turtle" http://localhost:8000/api/product/<id>`. The product's URI is
   the URL that serves it.

## 6. Evidence, including the weak spots (1 min)
Show the table in `RESULTS.md` (or the README): keyword gets 0.00 on paraphrases, semantic 0.95;
they tie on exact lookups. Then name the failures yourself: *"make music at home" returns the
turntable, not the studio monitors.*

## If something breaks
- **No results / "literal matches" banner:** the encoder is down. That is the designed fallback;
  say so, and use Strings mode.
- **Blank page:** the backend is not running (`/health` should answer on :8000).
- **Slow first search:** the model is still warming up; wait ~15 s.
