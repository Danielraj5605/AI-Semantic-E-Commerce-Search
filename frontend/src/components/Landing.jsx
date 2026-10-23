import { Fragment, useEffect, useRef, useState } from "react";
import SearchBar from "./SearchBar";
import GraphField from "./GraphField";
import Icon, { Logo } from "./Icon";
import { LayerCakeStack } from "./LayerCake";
import { EXAMPLE_QUERIES } from "../concepts";
import { getValidation } from "../api";

/**
 * The front door. It has one job (get a query typed) and a second (show, in
 * order, what happens to that query), so the page reads as the pipeline itself:
 * a sentence goes in, a ranked set of RDF resources comes out, and every fact in
 * it can be traced, proved and checked.
 */

/* ---- motion helpers ---------------------------------------------------- */

/** Adds `is-in` once the element scrolls into view; CSS does the rest. */
export function useReveal() {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          el.classList.add("is-in");
          io.disconnect();
        }
      },
      { threshold: 0.18 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return ref;
}

function CountUp({ value, decimals = 0, duration = 1100 }) {
  const [shown, setShown] = useState(0);
  const ref = useRef(null);
  useEffect(() => {
    if (value == null) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      setShown(value);
      return;
    }
    let raf = 0;
    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      io.disconnect();
      const start = performance.now();
      const tick = (now) => {
        const p = Math.min(1, (now - start) / duration);
        const eased = 1 - Math.pow(1 - p, 3);
        setShown(value * eased);
        if (p < 1) raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    });
    if (ref.current) io.observe(ref.current);
    return () => {
      io.disconnect();
      cancelAnimationFrame(raf);
    };
  }, [value, duration]);
  return <span ref={ref}>{value == null ? "—" : shown.toFixed(decimals)}</span>;
}

/** Words rise into place one after another. */
function Rise({ text, start = 0, className = "" }) {
  return text.split(" ").map((word, i) => (
    <Fragment key={i}>
      <span className={`rise ${className}`} style={{ "--d": `${start + i * 55}ms` }}>
        <span>{word}</span>
      </span>{" "}
    </Fragment>
  ));
}

/* ---- content ----------------------------------------------------------- */

const PIPELINE = [
  { k: "Ask", t: "A sentence becomes ?query", d: "Plain language, no keywords required. The same string is bound into the SPARQL the interface shows you.", code: "GET /api/search?q=…" },
  { k: "Encode", t: "Meaning as a vector", d: "all-MiniLM-L6-v2 maps the query into 384 dimensions, cached after the first load and degraded gracefully if it is down.", code: "384-d · L2 normalised" },
  { k: "Retrieve", t: "Nearest by cosine", d: "pgvector ranks products by similarity; a floor of 0.25 keeps unrelated items out instead of padding the page.", code: "1 − (e <=> q) ≥ 0.25" },
  { k: "Lift", t: "Rows become RDF", d: "A direct mapping publishes each row over schema.org, Dublin Core and PROV, in Turtle, RDF/XML or JSON-LD.", code: "Accept: text/turtle" },
  { k: "Reason", t: "The ontology adds what follows", d: "An OWL 2 RL-style reasoner entails superclasses, defined classes and inverses, and checks the catalogue for consistency.", code: "cax-sco · cls-def · cax-dw" },
  { k: "Trust", t: "Every claim can be checked", d: "Each inference has a proof tree, each match a measured confidence, each graph a signed digest.", code: "HMAC-SHA256 · PROV-O" },
];

function Pipeline() {
  const ref = useReveal();
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);
  useEffect(() => {
    if (paused || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const id = setInterval(() => setActive((a) => (a + 1) % PIPELINE.length), 2600);
    return () => clearInterval(id);
  }, [paused]);

  return (
    <section className="lp-section" id="pipeline" ref={ref}>
      <header className="lp-head reveal">
        <span className="lp-kicker">How it works</span>
        <h2 className="lp-h2">From a sentence to a proof, in six steps.</h2>
        <p className="lp-sub">
          Statistical semantics finds the candidates. Formal semantics describes them, reasons over
          them, and says how far each claim can be believed.
        </p>
      </header>

      <div
        className="pipe reveal"
        style={{ "--step": active, "--steps": PIPELINE.length }}
        onMouseLeave={() => setPaused(false)}
      >
        <div className="pipe__rail" aria-hidden="true">
          <span className="pipe__fill" />
        </div>
        <ol className="pipe__list">
          {PIPELINE.map((s, i) => (
            <li
              key={s.k}
              className={`pipe__step ${i === active ? "is-active" : ""} ${i < active ? "is-done" : ""}`}
              onMouseEnter={() => {
                setPaused(true);
                setActive(i);
              }}
            >
              <span className="pipe__dot" aria-hidden="true" />
              <span className="pipe__k">
                {String(i + 1).padStart(2, "0")} · {s.k}
              </span>
              <h3 className="pipe__t">{s.t}</h3>
              <p className="pipe__d">{s.d}</p>
              <code className="pipe__code">{s.code}</code>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

function Evidence() {
  const ref = useReveal();
  const [check, setCheck] = useState(null);
  useEffect(() => {
    getValidation().then(setCheck).catch(() => setCheck(null));
  }, []);

  const stats = [
    { v: 0.89, dec: 2, vs: "0.37", label: "Mean reciprocal rank", note: "semantic vs keyword, 30 labelled queries" },
    { v: 0.95, dec: 2, vs: "0.00", label: "On paraphrases", note: "where no word in the query appears in the product" },
    { v: check?.inferred_triples ?? null, dec: 0, label: "Triples inferred", note: check ? `from ${check.asserted_triples} asserted, by rule` : "reasoner offline" },
    { v: check?.products_checked ?? null, dec: 0, label: check?.conforms ? "Products conform" : "Products checked", note: "against the OWL ontology, every request" },
  ];

  return (
    <section className="lp-section" id="evidence" ref={ref}>
      <header className="lp-head reveal">
        <span className="lp-kicker">Evidence</span>
        <h2 className="lp-h2">Measured, not asserted.</h2>
        <p className="lp-sub">
          Retrieval is evaluated against labelled queries in <code>backend/eval</code>; the graph
          figures are computed live by the reasoner when this page loads.
        </p>
      </header>
      <div className="stats reveal">
        {stats.map((s) => (
          <div className="stat" key={s.label}>
            <div className="stat__v">
              <CountUp value={s.v} decimals={s.dec} />
              {s.vs && <span className="stat__vs">vs {s.vs}</span>}
            </div>
            <div className="stat__l">{s.label}</div>
            <div className="stat__n">{s.note}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

const TURTLE = `@prefix schema: <http://schema.org/> .
@prefix cat:    <http://example.org/ontology/catalog#> .
@prefix prov:   <http://www.w3.org/ns/prov#> .

ex:product/8f3a
    a                   schema:Product , cat:MensClothing ;
    schema:name         "Insulated Men's Parka"@en ;
    schema:brand        ex:brand/arcticwear ;
    schema:offers       [ a schema:Offer ;
                          schema:price "189.99"^^xsd:decimal ] ;
    prov:wasDerivedFrom ex:table/products .

# entailed by the reasoner, with a proof for each
ex:product/8f3a  a  cat:Clothing , cat:TopRated , cat:InStockProduct .`;

function highlight(src) {
  const re = /(#[^\n]*)|("(?:[^"\\]|\\.)*"(?:@[a-z-]+|\^\^[A-Za-z]+:[A-Za-z]+)?)|(<[^>\s]*>)|(@prefix)|\b([a-z]+:[A-Z][\w]*)|\b([a-z]+:[a-z][\w/]*)/g;
  const out = [];
  let last = 0, m, k = 0;
  while ((m = re.exec(src))) {
    if (m.index > last) out.push(src.slice(last, m.index));
    const cls = m[1] ? "c" : m[2] ? "lit" : m[3] ? "uri" : m[4] ? "kw" : m[5] ? "class" : "prop";
    const kind = cls === "prop" && /^(ex):/.test(m[0]) ? "uri" : cls;
    out.push(<span key={k++} className={`tk tk--${kind}`}>{m[0]}</span>);
    last = re.lastIndex;
  }
  out.push(src.slice(last));
  return out;
}

function Stack({ onConcepts }) {
  const ref = useReveal();
  return (
    <section className="lp-section" id="stack" ref={ref}>
      <header className="lp-head reveal">
        <span className="lp-kicker">The Semantic Web stack</span>
        <h2 className="lp-h2">Every layer, from identity to trust.</h2>
        <p className="lp-sub">
          Read bottom-up. Each layer means something only because the one beneath it settled identity,
          then syntax, then statements, then vocabulary.
        </p>
      </header>
      <div className="lp-split reveal">
        <div className="lp-split__a">
          <LayerCakeStack compact />
          <button className="btn btn--ghost" onClick={onConcepts}>
            Read what each layer does here <Icon name="arrowRight" size={14} />
          </button>
        </div>
        <figure className="window">
          <div className="window__bar">
            <span className="window__dots" aria-hidden="true"><i /><i /><i /></span>
            <span className="window__title">product.ttl · text/turtle</span>
          </div>
          <pre className="window__body"><code>{highlight(TURTLE)}</code></pre>
          <figcaption className="window__cap">
            A result is a description, not a tile: typed against an ontology, linked to its brand, and
            traceable to the row it came from.
          </figcaption>
        </figure>
      </div>
    </section>
  );
}

/* ---- page -------------------------------------------------------------- */

export default function Landing({ onSearch, onConcepts, themeToggle }) {
  return (
    <div className="lp">
      <nav className="lp-nav" aria-label="Primary">
        <a className="brand" href="#top" aria-label="CatalogueGraph">
          <Logo />
          <span className="brand__name">CatalogueGraph</span>
        </a>
        <div className="lp-nav__links">
          <a href="#pipeline">How it works</a>
          <a href="#evidence">Evidence</a>
          <a href="#stack">The stack</a>
          <button className="lp-nav__btn" onClick={onConcepts}>Concepts</button>
        </div>
        {themeToggle}
      </nav>

      <header className="hero" id="top">
        <GraphField />
        <div className="hero__veil" aria-hidden="true" />
        <div className="hero__inner">
          <p className="hero__eyebrow">
            <span className="pulse" aria-hidden="true" />
            AI Semantic E-Commerce Search · 21CSE452T
          </p>
          <h1 className="hero__title">
            <Rise text="Search a catalogue by what you" />
            <span className="rise hero__serif" style={{ "--d": "330ms" }}>
              <span>mean.</span>
            </span>
          </h1>
          <p className="hero__lede fade" style={{ "--d": "520ms" }}>
            Products are found by meaning, then published as a knowledge graph: every result has a URI,
            a type in an OWL ontology, facts the reasoner can prove, and a provenance trail you can verify.
          </p>
          <div className="hero__search fade" style={{ "--d": "640ms" }}>
            <SearchBar onSearch={onSearch} size="lg" />
          </div>
          <div className="hero__examples fade" style={{ "--d": "760ms" }}>
            <span className="hero__try">Try</span>
            {EXAMPLE_QUERIES.map((e) => (
              <button key={e.text} className="example" onClick={() => onSearch(e.text)}>
                <span className="example__text">{e.text}</span>
                <span className="example__note">{e.note}</span>
              </button>
            ))}
          </div>
        </div>
        <a className="hero__scroll fade" style={{ "--d": "1000ms" }} href="#pipeline">
          <span>How it works</span>
          <Icon name="chevronDown" size={14} />
        </a>
      </header>

      <Pipeline />
      <Evidence />
      <Stack onConcepts={onConcepts} />

      <footer className="lp-foot">
        <div className="lp-foot__brand">
          <Logo size={18} />
          <span>CatalogueGraph</span>
        </div>
        <p>
          A relational catalogue, searched by meaning and published as linked data. FastAPI, pgvector,
          sentence-transformers, rdflib, React.
        </p>
        <span className="lp-foot__course">Semantic Web · 21CSE452T</span>
      </footer>
    </div>
  );
}
