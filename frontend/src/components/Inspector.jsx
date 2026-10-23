import { useMemo, useState } from "react";
import {
  NAMESPACES,
  NAMESPACE_NOTES,
  MAPPING_RULES,
  resultsToTriples,
  toTurtle,
  toRDFXML,
  toJSONLD,
  buildSPARQL,
  buildClassTree,
  ontologyAxioms,
} from "../rdf";
import LogicPanel from "./LogicPanel";

/**
 * The inspector is where the answer stops being a page of products and becomes
 * a document you could hand to another machine.
 *
 * Unit 5 is explicit that the same graph has several concrete syntaxes; showing
 * them side by side over the *current* result set makes that concrete instead of
 * theoretical. The SPARQL tab shows the query the interface would have issued
 * against a triple store, and the Mapping tab shows the rules that got the
 * relational rows into the graph in the first place (Unit 4).
 */

const TABS = [
  { id: "turtle", label: "Turtle", hint: "text/turtle" },
  { id: "rdfxml", label: "RDF/XML", hint: "application/rdf+xml" },
  { id: "jsonld", label: "JSON-LD", hint: "application/ld+json" },
  { id: "sparql", label: "SPARQL", hint: "the equivalent query" },
  { id: "mapping", label: "Mapping", hint: "relational → RDF" },
  { id: "axioms", label: "Axioms", hint: "the local ontology" },
  { id: "logic", label: "Logic", hint: "OWL, rules and validation" },
  { id: "prefixes", label: "Prefixes", hint: "vocabularies in use" },
];

function CodePane({ text, language }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };

  const lines = text.split("\n").length;

  return (
    <div className="code">
      <div className="code__bar">
        <span className="code__meta">
          {language} · {lines} lines
        </span>
        <button className="code__copy" onClick={copy}>
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="code__pre">
        <code>{text}</code>
      </pre>
    </div>
  );
}

export default function Inspector({ open, onClose, results, query, filters, mode, categories, initialTab }) {
  const [tab, setTab] = useState(initialTab || "turtle");

  const graph = useMemo(() => resultsToTriples(results || []), [results]);
  const classTree = useMemo(() => buildClassTree(categories || []), [categories]);
  const axioms = useMemo(() => ontologyAxioms(classTree), [classTree]);

  const body = useMemo(() => {
    switch (tab) {
      case "turtle":
        return <CodePane text={toTurtle(graph)} language="text/turtle" />;
      case "rdfxml":
        return <CodePane text={toRDFXML(graph)} language="application/rdf+xml" />;
      case "jsonld":
        return <CodePane text={toJSONLD(results || [])} language="application/ld+json" />;
      case "sparql":
        return (
          <>
            <p className="panel__lede">
              What the interface is asking, written as it would be asked of a SPARQL
              endpoint. Every constraint you set in the left rail appears here as a
              graph pattern or a <code>FILTER</code>.
            </p>
            <CodePane text={buildSPARQL(query, filters, mode)} language="application/sparql-query" />
          </>
        );
      case "mapping":
        return (
          <>
            <p className="panel__lede">
              A direct mapping from the relational catalogue to RDF — Unit 4&rsquo;s
              &ldquo;Exposing Relational Databases&rdquo;. The store stays relational; the graph
              is a published view over it.
            </p>
            <table className="grid">
              <thead>
                <tr>
                  <th>Column</th>
                  <th>Predicate</th>
                  <th>Treatment</th>
                </tr>
              </thead>
              <tbody>
                {MAPPING_RULES.map((r) => (
                  <tr key={r.column}>
                    <td>
                      <code>{r.column}</code>
                    </td>
                    <td>
                      <span className="term term--prop">{r.predicate}</span>
                    </td>
                    <td className="grid__note">{r.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        );
      case "axioms":
        return (
          <>
            <p className="panel__lede">
              The local ontology, asserted from the category table. Shallow by design — a
              terminology plus subsumption, which is the level most working vocabularies
              actually sit at.
            </p>
            <table className="grid">
              <thead>
                <tr>
                  <th>Subject</th>
                  <th>Predicate</th>
                  <th>Object</th>
                </tr>
              </thead>
              <tbody>
                {axioms.map((a, i) => (
                  <tr key={i}>
                    <td>
                      <span className="term term--class">{a.subject}</span>
                    </td>
                    <td>
                      <span className="term term--prop">{a.predicate}</span>
                    </td>
                    <td>
                      <span className="term term--class">{a.object}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        );
      case "logic":
        return <LogicPanel />;
      case "prefixes":
      default:
        return (
          <>
            <p className="panel__lede">
              Namespaces keep terms from colliding — the reason a QName is short and a URI
              is long. Reused vocabularies are preferred to invented ones; only{" "}
              <code>cat:</code> and <code>ex:</code> are local.
            </p>
            <table className="grid">
              <thead>
                <tr>
                  <th>Prefix</th>
                  <th>Namespace URI</th>
                  <th>Why it is here</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(NAMESPACES).map(([p, ns]) => (
                  <tr key={p}>
                    <td>
                      <span className="term term--class">{p}:</span>
                    </td>
                    <td>
                      <code className="grid__uri">{ns}</code>
                    </td>
                    <td className="grid__note">{NAMESPACE_NOTES[p]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        );
    }
  }, [tab, graph, results, query, filters, mode, axioms]);

  if (!open) return null;

  return (
    <div className="drawer" role="dialog" aria-modal="true" aria-label="Graph inspector">
      <div className="drawer__scrim" onClick={onClose} />
      <div className="drawer__panel">
        <header className="drawer__head">
          <div>
            <h2 className="drawer__title">Inspect the graph</h2>
            <p className="drawer__sub">
              {graph.length} statements over {results?.length || 0} resources
            </p>
          </div>
          <button className="drawer__close" onClick={onClose} aria-label="Close inspector">
            ✕
          </button>
        </header>

        <nav className="drawer__tabs">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={tab === t.id ? "is-on" : ""}
              onClick={() => setTab(t.id)}
              title={t.hint}
            >
              {t.label}
            </button>
          ))}
        </nav>

        <div className="drawer__body">{body}</div>
      </div>
    </div>
  );
}
