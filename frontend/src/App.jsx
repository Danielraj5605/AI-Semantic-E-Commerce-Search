import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { searchProducts, keywordSearch, getFilters, getSimilar } from "./api";
import { toJSONLD, resultsToTriples, categoryURI } from "./rdf";
import { describeService, EXAMPLE_QUERIES } from "./concepts";

import SearchBar from "./components/SearchBar";
import OntologyRail from "./components/OntologyRail";
import ResourceCard from "./components/ResourceCard";
import Inspector from "./components/Inspector";
import ConceptsDrawer, { LayerCakeStack } from "./components/LayerCake";
import { ResultGraph } from "./components/GraphView";
import Term from "./components/Term";

import "./index.css";

/* ============================================================
   THEME
   Respects the OS by default; the toggle is a deliberate override
   and is remembered, which is the only thing localStorage is used for.
   ============================================================ */

function useTheme() {
  // Dark by default rather than following the OS: this is a dark-first
  // design, and a machine set to light mode should still see it as intended
  // on first load. Light is an explicit choice, and it is remembered.
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem("cg-theme") === "light" ? "light" : "dark";
    } catch {
      return "dark";
    }
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("cg-theme", theme);
    } catch {
      /* private mode — the preference simply will not persist */
    }
  }, [theme]);

  return [theme, setTheme];
}

/* ============================================================
   PUBLISHING THE ANSWER  (Unit 1 — annotation; Unit 5 — JSON-LD)
   The result set is written into the document head as JSON-LD, so the
   page is machine-readable to anything that crawls it. This is not
   decoration: it is the one place the app is genuinely a Semantic Web
   participant rather than a viewer of one.
   ============================================================ */

function useJSONLDEmbed(results) {
  const nodeRef = useRef(null);

  useEffect(() => {
    // No results means no graph to publish. An empty ld+json block is not valid
    // JSON, so the element is removed rather than blanked.
    if (!results?.length) {
      nodeRef.current?.remove();
      nodeRef.current = null;
      return;
    }
    if (!nodeRef.current) {
      const el = document.createElement("script");
      el.type = "application/ld+json";
      el.id = "results-jsonld";
      document.head.appendChild(el);
      nodeRef.current = el;
    }
    nodeRef.current.textContent = toJSONLD(results);
  }, [results]);

  useEffect(
    () => () => {
      nodeRef.current?.remove();
      nodeRef.current = null;
    },
    []
  );
}

/* ============================================================
   LANDING
   ============================================================ */

function Landing({ onSearch, onConcepts }) {
  return (
    <div className="landing">
      <div className="landing__inner">
        <p className="landing__eyebrow">
          <span className="dot" /> 21CSE452T · Semantic Web · catalogue as a knowledge graph
        </p>

        <h1 className="landing__title">
          A product catalogue,
          <br />
          <em>published as a graph.</em>
        </h1>

        <p className="landing__lede">
          The rows sit in PostgreSQL. Everything you see is a view over them in RDF —
          every product carries a URI, is typed against an ontology, describes itself in
          schema.org terms, and states where its facts came from. Ask in plain language;
          read the answer as triples.
        </p>

        <div className="landing__search">
          <SearchBar onSearch={onSearch} size="lg" />
        </div>

        <div className="landing__examples">
          {EXAMPLE_QUERIES.map((e) => (
            <button key={e.text} className="example" onClick={() => onSearch(e.text)}>
              <span className="example__text">{e.text}</span>
              <span className="example__note">{e.note}</span>
            </button>
          ))}
        </div>

        <div className="landing__split">
          <section className="landing__cake">
            <h2 className="landing__h2">The stack, and how far this climbs</h2>
            <LayerCakeStack compact />
            <button className="linkbtn" onClick={onConcepts}>
              Read the full mapping →
            </button>
          </section>

          <section className="landing__sample">
            <h2 className="landing__h2">What a result actually is</h2>
            <pre className="code__pre code__pre--inline">
              <code>{`@prefix schema: <http://schema.org/> .
@prefix cat:    <http://example.org/ontology/catalog#> .

ex:product/8f3a-…
    rdf:type            schema:Product ;
    rdf:type            cat:Outerwear ;
    schema:name         "Insulated Parka"@en ;
    schema:brand        ex:brand/northline ;
    schema:offers       [ schema:price "189.00"^^xsd:decimal ] ;
    cat:similarityScore "0.8134"^^xsd:double ;
    prov:wasDerivedFrom ex:table/products .`}</code>
            </pre>
            <p className="landing__caption">
              Subject, predicate, object — and a provenance statement, so the claim can be
              traced rather than taken on faith.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   APP
   ============================================================ */

export default function App() {
  const [theme, setTheme] = useTheme();

  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [mode, setMode] = useState("semantic");
  const [filterOptions, setFilterOptions] = useState(null);
  const [active, setActive] = useState({});
  const [started, setStarted] = useState(false);

  const [view, setView] = useState("resources"); // resources | graph
  const [inspector, setInspector] = useState(null); // null | tab id
  const [concepts, setConcepts] = useState(false);

  const rows = results?.results || [];
  useJSONLDEmbed(rows);

  useEffect(() => {
    getFilters()
      .then(setFilterOptions)
      .catch((e) => console.warn("Ontology unavailable:", e));
  }, []);

  const run = useCallback(
    async (q, nextMode = mode, constraints = active) => {
      const value = (q || "").trim();
      if (!value) return;

      setQuery(value);
      setStarted(true);
      setLoading(true);
      setError(null);

      try {
        const fn = nextMode === "keyword" ? keywordSearch : searchProducts;
        setResults(await fn(value, { ...constraints, limit: 40 }));
      } catch (err) {
        setError(err.message || "The service did not answer. Is the backend running?");
        setResults(null);
      } finally {
        setLoading(false);
      }
    },
    [mode, active]
  );

  const findSimilar = async (product) => {
    setLoading(true);
    setError(null);
    try {
      const res = await getSimilar(product.product_id);
      setResults({ ...res, similar: true, seedName: product.name });
      setView("resources");
    } catch (err) {
      setError(err.message || "Could not find similar products.");
    } finally {
      setLoading(false);
    }
  };

  const changeConstraint = (key, value) => {
    const next = { ...active, [key]: value };
    if (value === null || value === "") delete next[key];
    setActive(next);
    if (query) run(query, mode, next);
  };

  const clearConstraints = () => {
    setActive({});
    if (query) run(query, mode, {});
  };

  const changeMode = (next) => {
    setMode(next);
    if (query) run(query, next, active);
  };

  const service = useMemo(() => describeService(mode), [mode]);
  const statementCount = useMemo(() => resultsToTriples(rows).length, [rows]);
  const activeCount = Object.keys(active).length;

  const goHome = () => {
    setStarted(false);
    setResults(null);
    setQuery("");
    setActive({});
    setError(null);
  };

  /* ---- Landing ---------------------------------------------------- */
  if (!started) {
    return (
      <>
        <ThemeToggle theme={theme} setTheme={setTheme} floating />
        <Landing onSearch={(q) => run(q)} onConcepts={() => setConcepts(true)} />
        <ConceptsDrawer open={concepts} onClose={() => setConcepts(false)} />
      </>
    );
  }

  /* ---- Workspace -------------------------------------------------- */
  return (
    <div className="app">
      <header className="topbar">
        <button className="mark" onClick={goHome} aria-label="Back to the start">
          <span className="mark__glyph" aria-hidden="true">
            ⬡
          </span>
          <span className="mark__text">
            Catalogue<span className="mark__thin">Graph</span>
          </span>
        </button>

        <div className="topbar__search">
          <SearchBar onSearch={(q) => run(q)} initial={query} />
        </div>

        <div className="topbar__right">
          <div className="segmented" role="group" aria-label="Retrieval strategy">
            <button
              className={mode === "semantic" ? "is-on" : ""}
              onClick={() => changeMode("semantic")}
              title="Vector similarity — matches meaning"
            >
              Meaning
            </button>
            <button
              className={mode === "keyword" ? "is-on" : ""}
              onClick={() => changeMode("keyword")}
              title="SQL substring match — the syntactic baseline"
            >
              Strings
            </button>
          </div>
          <ThemeToggle theme={theme} setTheme={setTheme} />
        </div>
      </header>

      {/* ---- Service descriptor (Unit 3) ------------------------------ */}
      <div className="servicebar">
        <span className="servicebar__label">Service invoked</span>
        <Term term={{ term: "uri", value: service.name }} role="class" />
        <code className="servicebar__op">{service.operation}</code>
        <span className="servicebar__sep">·</span>
        <span className="servicebar__method">{service.method}</span>
        <span className="servicebar__spacer" />
        <button className="linkbtn" onClick={() => setConcepts(true)}>
          Concepts
        </button>
        <button className="linkbtn linkbtn--strong" onClick={() => setInspector("turtle")}>
          Inspect graph
        </button>
      </div>

      <div className="workspace">
        <OntologyRail
          filters={filterOptions}
          active={active}
          onChange={changeConstraint}
          onClear={clearConstraints}
          onShowAxioms={() => setInspector("axioms")}
        />

        <main className="stage">
          {/* ---- Answer header ---------------------------------------- */}
          {results && !loading && (
            <div className="answer">
              <div className="answer__line">
                <h1 className="answer__count">
                  {results.total}
                  <span className="answer__count-unit">
                    {results.total === 1 ? " resource" : " resources"}
                  </span>
                </h1>
                <p className="answer__detail">
                  {results.similar ? (
                    <>nearest to <code className="answer__q">“{results.seedName}”</code> by embedding</>
                  ) : (
                    <>bound to <code className="answer__q">?query “{results.query}”</code></>
                  )}{" "}
                  · {statementCount} statements
                  {!results.similar && (
                    <>
                      {" "}·{" "}
                      <button className="linkbtn" onClick={() => setInspector("sparql")}>
                        see the SPARQL
                      </button>
                    </>
                  )}
                </p>
              </div>

              <div className="answer__tools">
                {active.category && (
                  <span className="pill">
                    <Term term={{ term: "uri", value: categoryURI(active.category) }} role="class" />
                    <button onClick={() => changeConstraint("category", null)} aria-label="Remove class constraint">
                      ✕
                    </button>
                  </span>
                )}
                <div className="segmented segmented--sm" role="group" aria-label="View">
                  <button className={view === "resources" ? "is-on" : ""} onClick={() => setView("resources")}>
                    Resources
                  </button>
                  <button className={view === "graph" ? "is-on" : ""} onClick={() => setView("graph")}>
                    Graph
                  </button>
                </div>
              </div>
            </div>
          )}

          {!error && results && mode === "semantic" && results.search_type === "keyword" && (
            <div className="notice">
              <h2 className="notice__title">Showing literal matches</h2>
              <p className="notice__body">
                The meaning encoder is unavailable, so this answer comes from plain string
                matching and carries no similarity scores.
              </p>
            </div>
          )}

          {error && (
            <div className="notice notice--bad">
              <h2 className="notice__title">The service did not respond</h2>
              <p className="notice__body">{error}</p>
              <p className="notice__hint">
                Graceful degradation is a stated requirement — try <strong>Strings</strong> mode,
                which needs no encoder in the request path.
              </p>
            </div>
          )}

          {loading && <Skeleton />}

          {!loading && rows.length > 0 && view === "resources" && (
            <div className="results">
              {rows.map((r, i) => (
                <ResourceCard
                  key={r.product.product_id}
                  result={r}
                  query={results.query}
                  mode={results.search_type || mode}
                  rank={i + 1}
                  onSimilar={findSimilar}
                />
              ))}
            </div>
          )}

          {!loading && rows.length > 0 && view === "graph" && (
            <div className="results results--graph">
              <ResultGraph results={rows} query={results.query} />
            </div>
          )}

          {!loading && results && rows.length === 0 && (
            <div className="notice">
              <h2 className="notice__title">No resource satisfies the query</h2>
              <p className="notice__body">
                Nothing in the graph matched <code>“{results.query}”</code>
                {activeCount > 0 ? " under the current constraints." : "."}
              </p>
              <p className="notice__hint">
                An empty answer is a legitimate answer — the catalogue may simply hold no such
                thing. Before concluding that, try widening it:
              </p>
              <div className="notice__actions">
                {active.category && (
                  <button className="chip" onClick={() => changeConstraint("category", null)}>
                    Drop <span className="term term--class">{categoryURI(active.category)}</span>
                  </button>
                )}
                {active.brand && (
                  <button className="chip" onClick={() => changeConstraint("brand", null)}>
                    Drop brand “{active.brand}”
                  </button>
                )}
                {activeCount > 1 && (
                  <button className="chip" onClick={clearConstraints}>
                    Clear all {activeCount} constraints
                  </button>
                )}
                {mode === "keyword" && (
                  <button className="chip" onClick={() => changeMode("semantic")}>
                    Try Meaning instead of Strings
                  </button>
                )}
              </div>
            </div>
          )}
        </main>
      </div>

      <Inspector
        open={inspector !== null}
        initialTab={inspector || "turtle"}
        onClose={() => setInspector(null)}
        results={rows}
        query={query}
        filters={active}
        mode={mode}
        categories={filterOptions?.categories}
      />
      <ConceptsDrawer open={concepts} onClose={() => setConcepts(false)} />
    </div>
  );
}

/* ============================================================
   SMALL PIECES
   ============================================================ */

function ThemeToggle({ theme, setTheme, floating = false }) {
  const next = theme === "dark" ? "light" : "dark";
  return (
    <button
      className={`themebtn ${floating ? "themebtn--float" : ""}`}
      onClick={() => setTheme(next)}
      title={`Switch to ${next} theme`}
      aria-label={`Theme: ${theme}. Switch to ${next}.`}
    >
      {theme === "dark" ? "☾" : "☀"}
    </button>
  );
}

function Skeleton({ count = 5 }) {
  return (
    <div className="results" aria-busy="true" aria-label="Resolving">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="res res--skeleton" style={{ "--i": i }}>
          <div className="sk sk--uri" />
          <div className="res__body">
            <div className="sk sk--thumb" />
            <div className="res__main">
              <div className="sk sk--line sk--w40" />
              <div className="sk sk--line sk--w80" />
              <div className="sk sk--line sk--w60" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
