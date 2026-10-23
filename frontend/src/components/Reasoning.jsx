import { useEffect, useState } from "react";
import { getInferences, getProof, getProvenance, verifyGraph } from "../api";

/**
 * What the reasoner derived about one resource, why each fact holds, and whether
 * the description can be trusted not to have been altered.
 *
 * Everything shown here is computed by the API from the catalogue row plus the
 * ontology: no text in this panel is canned. Each derived fact is expandable into
 * its proof tree, whose leaves are either catalogue rows or ontology axioms.
 */

function ProofNode({ node, depth = 0 }) {
  const derived = node.kind === "derived";
  return (
    <li className={`ptree__node ptree__node--${node.kind}`}>
      <div className="ptree__line">
        <code className="ptree__stmt">{node.statement}</code>
        {derived ? (
          <span className="ptree__rule" title={node.rule_text}>
            {node.rule} · {node.rule_name}
            {node.note ? ` · ${node.note}` : ""}
          </span>
        ) : (
          <span className={`ptree__leaf ptree__leaf--${node.kind}`}>
            {node.kind === "axiom" ? "ontology axiom" : "catalogue row"}
          </span>
        )}
      </div>
      {derived && (
        <ul className="ptree">
          {node.premises.map((p, i) => (
            <ProofNode key={i} node={p} depth={depth + 1} />
          ))}
        </ul>
      )}
    </li>
  );
}

function ProofItem({ item }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="infer">
      <button className="infer__head" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <span className="infer__caret">{open ? "▾" : "▸"}</span>
        <code className="infer__stmt">{item.conclusion}</code>
        <span className="infer__meta">
          {item.rule} · {item.depth} step{item.depth === 1 ? "" : "s"} · {item.grounded_in} grounding fact
          {item.grounded_in === 1 ? "" : "s"}
        </span>
      </button>
      {open && (
        <ul className="ptree ptree--root">
          <ProofNode node={item.proof} />
        </ul>
      )}
    </li>
  );
}

function Provenance({ productId }) {
  const [prov, setProv] = useState(null);
  const [check, setCheck] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let live = true;
    getProvenance(productId)
      .then((p) => live && setProv(p))
      .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [productId]);

  const run = async (tamper) => {
    const turtle = tamper
      ? prov.graph_turtle.replace(/(schema:price\s+)[0-9.]+/, (_, lead) => `${lead}0.01`)
      : prov.graph_turtle;
    try {
      const r = await verifyGraph(turtle, prov.signature, productId);
      setCheck({ ...r, tampered: tamper && turtle !== prov.graph_turtle });
    } catch (e) {
      setError(e.message);
    }
  };

  if (error) return <p className="res__panel-note">Provenance unavailable: {error}</p>;
  if (!prov) return <p className="res__panel-note">Loading provenance…</p>;

  return (
    <div className="prov">
      <dl className="prov__facts">
        <div>
          <dt>sha-256 of the canonical graph</dt>
          <dd>
            <code>{prov.digest}</code>
          </dd>
        </div>
        <div>
          <dt>{prov.signature_algorithm} signature</dt>
          <dd>
            <code>{prov.signature}</code>
          </dd>
        </div>
        <div>
          <dt>key</dt>
          <dd>
            {prov.key_source}
            {prov.key_source === "development-default" && " (public — set TRUST_KEY for a real signature)"}
          </dd>
        </div>
        <div>
          <dt>inferences recorded</dt>
          <dd>{prov.inferences_recorded}, each reified with prov:wasGeneratedBy and its rule</dd>
        </div>
      </dl>
      <div className="prov__actions">
        <button className="linkbtn" onClick={() => run(false)}>
          Verify this graph
        </button>
        <button className="linkbtn" onClick={() => run(true)}>
          Change the price to $0.01 and verify
        </button>
      </div>
      {check && (
        <p className={`prov__result prov__result--${check.signature_valid ? "ok" : "bad"}`} role="status">
          {check.signature_valid
            ? "Signature valid — the graph is exactly what was signed."
            : check.tampered
              ? "Signature INVALID — one changed triple was detected."
              : "Signature INVALID."}
          {check.matches_catalogue === false && " It also no longer matches the catalogue."}
        </p>
      )}
    </div>
  );
}

export default function Reasoning({ productId }) {
  const [inf, setInf] = useState(null);
  const [proofs, setProofs] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let live = true;
    setInf(null);
    setProofs(null);
    setError(null);
    Promise.all([getInferences(productId), getProof(productId)])
      .then(([i, p]) => {
        if (!live) return;
        setInf(i);
        setProofs(p.proofs);
      })
      .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [productId]);

  if (error) return <p className="res__panel-note">The reasoner is unavailable: {error}</p>;
  if (!inf || !proofs) return <p className="res__panel-note">Reasoning…</p>;

  const byRule = {};
  inf.inferred.forEach((i) => (byRule[i.rule] = (byRule[i.rule] || 0) + 1));

  return (
    <div className="reasoning">
      <p className="reasoning__sum">
        <strong>{inf.asserted}</strong> asserted triples entail <strong>{inf.inferred.length}</strong> more
        {Object.keys(byRule).length > 0 && (
          <span className="reasoning__rules">
            {" "}
            ({Object.entries(byRule)
              .map(([r, n]) => `${n}× ${r}`)
              .join(", ")})
          </span>
        )}
        . {inf.consistent ? "Consistent with the ontology." : `${inf.violations.length} violation(s).`}
      </p>

      {!inf.consistent && (
        <ul className="reasoning__violations">
          {inf.violations.map((v, i) => (
            <li key={i}>
              <code>{v.rule}</code> {v.message}
            </li>
          ))}
        </ul>
      )}

      <h4 className="reasoning__h">Inferred facts — open one for its proof</h4>
      <ul className="infer-list">
        {proofs.map((p) => (
          <ProofItem key={p.conclusion} item={p} />
        ))}
      </ul>

      <h4 className="reasoning__h">Provenance and integrity</h4>
      <Provenance productId={productId} />
    </div>
  );
}
