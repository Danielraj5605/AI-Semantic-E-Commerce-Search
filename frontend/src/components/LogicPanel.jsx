import { useEffect, useState } from "react";
import { getOntology, getRules, getValidation, ontologyUrl } from "../api";

/**
 * The ontology as the reasoner actually holds it (OWL, Unit 2), the rules it
 * applies (Logic), and the result of checking the whole catalogue against it.
 * All of it is fetched from the API; nothing here is hard-coded prose.
 */

const short = (q) => q;
const DERIVES = new Set(["scm-sco", "cax-sco", "prp-dom", "prp-rng", "prp-inv", "cls-def"]);

export default function LogicPanel() {
  const [onto, setOnto] = useState(null);
  const [rules, setRules] = useState(null);
  const [check, setCheck] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let live = true;
    Promise.all([getOntology(), getRules(), getValidation()])
      .then(([o, r, v]) => {
        if (!live) return;
        setOnto(o);
        setRules(r);
        setCheck(v);
      })
      .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, []);

  if (error) return <p className="panel__lede">The ontology service is unavailable: {error}</p>;
  if (!onto) return <p className="panel__lede">Loading the ontology and checking the catalogue…</p>;

  const disjoint = onto.classes.filter((c) => c.disjoint_with.length);

  return (
    <>
      <section className={`verdict verdict--${check.conforms ? "ok" : "bad"}`} role="status">
        <strong>{check.conforms ? "The catalogue conforms to its ontology." : "The catalogue violates its ontology."}</strong>
        <span>
          {" "}
          {check.products_checked} products · {check.asserted_triples} asserted triples ·{" "}
          {check.inferred_triples} inferred ({check.inferred_types} typings)
        </span>
        {!check.conforms && (
          <ul className="reasoning__violations">
            {check.violations.slice(0, 8).map((v, i) => (
              <li key={i}>
                <code>{v.rule}</code> {v.subject} {v.message}
              </li>
            ))}
          </ul>
        )}
      </section>

      <p className="panel__lede">
        Download the ontology as{" "}
        {["ttl", "rdf", "jsonld"].map((f, i) => (
          <span key={f}>
            {i > 0 && " · "}
            <a href={ontologyUrl(f)} target="_blank" rel="noreferrer">
              {f}
            </a>
          </span>
        ))}
        . It is OWL 2 RL-style: every axiom below is one the reasoner applies.
      </p>

      <h3 className="section__title">Rules applied</h3>
      <table className="grid">
        <thead>
          <tr>
            <th>Rule</th>
            <th>What it does</th>
            <th>Result</th>
          </tr>
        </thead>
        <tbody>
          {rules.map((r) => (
            <tr key={r.id}>
              <td>
                <span className="term term--prop">{r.id}</span> {r.name}
              </td>
              <td className="grid__note">{r.text}</td>
              <td>
                {DERIVES.has(r.id)
                  ? `${check.by_rule[r.id] ?? 0} derived`
                  : `${check.violations.filter((v) => v.rule === r.id).length} violations`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3 className="section__title">Defined classes (membership is inferred)</h3>
      <table className="grid">
        <thead>
          <tr>
            <th>Class</th>
            <th>Equivalent to a Product with</th>
            <th>Meaning</th>
          </tr>
        </thead>
        <tbody>
          {onto.defined_classes.map((d) => (
            <tr key={d.class}>
              <td>
                <span className="term term--class">{d.class}</span>
              </td>
              <td className="grid__note">
                {d.path.map(short).join(" → ")} {d.test.kind === "min" ? `≥ ${d.test.value}` : `= ${d.test.value}`}
              </td>
              <td className="grid__note">{d.comment}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3 className="section__title">Properties</h3>
      <table className="grid">
        <thead>
          <tr>
            <th>Property</th>
            <th>Kind</th>
            <th>Domain → range</th>
            <th>Inverse</th>
          </tr>
        </thead>
        <tbody>
          {onto.properties.map((p) => (
            <tr key={p.qname}>
              <td>
                <span className="term term--prop">{p.qname}</span>
              </td>
              <td className="grid__note">{p.kind}</td>
              <td className="grid__note">
                {p.domain.join(", ")} → {p.range.join(", ")}
              </td>
              <td className="grid__note">{p.inverse_of.join(", ") || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3 className="section__title">Restrictions and disjointness</h3>
      <table className="grid">
        <tbody>
          {onto.restrictions.map((r, i) => (
            <tr key={i}>
              <td>
                <span className="term term--class">{r.class}</span>
              </td>
              <td className="grid__note">
                owl:{r.kind} {r.value} on <span className="term term--prop">{r.property}</span>
              </td>
            </tr>
          ))}
          {disjoint.map((c) => (
            <tr key={c.qname}>
              <td>
                <span className="term term--class">{c.qname}</span>
              </td>
              <td className="grid__note">owl:disjointWith {c.disjoint_with.join(", ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
