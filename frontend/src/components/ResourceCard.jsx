import { useEffect, useMemo, useRef, useState } from "react";
import { productToTriples, productURI, categoryURI } from "../rdf";
import { trustBand, proofSteps, measuredConfidence } from "../concepts";
import Reasoning from "./Reasoning";
import { ResourceGraph } from "./GraphView";
import Term from "./Term";
import { recordClick, getCalibration } from "../api";
import Icon from "./Icon";

/**
 * A result is presented as a *resource*, not a product tile: it is announced by
 * its URI, its assertions can be read as triples, the belief attached to it is
 * stated rather than implied, and the reasoning that produced it is available
 * on demand (the proof layer of the cake, as far as this system can honour it).
 */

const money = (v) => (v == null ? "—" : `$${Number(v).toFixed(2)}`);

function Stars({ value = 0 }) {
  const full = Math.round(value);
  return (
    <span className="stars" aria-label={`${value.toFixed(1)} out of 5`}>
      {[0, 1, 2, 3, 4].map((i) => (
        <Icon key={i} name="star" size={12} fill className={i < full ? "stars__on" : "stars__off"} />
      ))}
    </span>
  );
}

export default function ResourceCard({ result, query, mode, rank, onSimilar, initialTab = null }) {
  const { product, score } = result;
  const [tab, setTab] = useState(initialTab); // null | 'triples' | 'graph' | 'proof' | 'reasoning'
  const [imgFailed, setImgFailed] = useState(false);

  const triples = useMemo(() => productToTriples(product, score), [product, score]);
  const ownTriples = useMemo(
    () => triples.filter((t) => t.s.value === productURI(product)),
    [triples, product]
  );
  const trust = trustBand(score, mode);
  const [calibration, setCalibration] = useState(null);
  useEffect(() => {
    getCalibration().then(setCalibration);
  }, []);
  const measured = mode === "semantic" ? measuredConfidence(score, calibration) : null;
  const proof = useMemo(() => proofSteps(result, query, mode), [result, query, mode]);

  const clicked = useRef(false);
  const toggle = (next) => {
    // Opening a result is the click signal; count it once per card.
    if (!clicked.current) {
      clicked.current = true;
      recordClick(query, product.product_id);
    }
    setTab((cur) => (cur === next ? null : next));
  };

  return (
    <article className="res" style={{ "--i": Math.min(rank - 1, 12) }} aria-labelledby={`res-${product.product_id}`}>
      {/* ---- URI header: identity comes first ------------------------- */}
      <header className="res__uri">
        <span className="res__rank">{String(rank).padStart(2, "0")}</span>
        <code className="res__uri-text" title={productURI(product)}>
          {productURI(product)}
        </code>
        <span className={`belief belief--${trust.level}`} title={measured ? `${trust.basis} ${measured.text}.` : trust.basis}>
          {trust.label}
          {score != null && mode === "semantic" && (
            <>
              <span className="belief__meter" aria-hidden="true">
                <span style={{ "--v": Math.max(0, Math.min(1, score / 0.75)) }} />
              </span>
              <span className="belief__score">{score.toFixed(3)}</span>
            </>
          )}
        </span>
      </header>

      <div className="res__body">
        <div className="res__thumb">
          {product.image_url && !imgFailed ? (
            <img
              src={product.image_url}
              alt=""
              loading="lazy"
              onError={() => setImgFailed(true)}
            />
          ) : (
            <span className="res__thumb-fallback" aria-hidden="true">
              <Icon name="image" size={22} />
            </span>
          )}
        </div>

        <div className="res__main">
          {product.category_name && (
            <div className="res__type">
              <span className="term term--prop">rdf:type</span>
              <Term
                term={{ term: "uri", value: categoryURI(product.category_name) }}
                role="class"
              />
            </div>
          )}

          <h3 className="res__name" id={`res-${product.product_id}`}>
            {product.name}
          </h3>

          {product.description && <p className="res__desc">{product.description}</p>}

          <dl className="res__facts">
            <div className="fact">
              <dt>schema:price</dt>
              <dd className="fact__strong">{money(product.price)}</dd>
            </div>
            <div className="fact">
              <dt>schema:ratingValue</dt>
              <dd>
                <Stars value={product.rating_avg || 0} />
                <span className="fact__muted">{(product.rating_avg || 0).toFixed(1)}</span>
              </dd>
            </div>
            {product.brand && (
              <div className="fact">
                <dt>schema:brand</dt>
                <dd>{product.brand}</dd>
              </div>
            )}
            <div className="fact">
              <dt>schema:availability</dt>
              <dd className={product.stock_quantity > 0 ? "fact__ok" : "fact__no"}>
                {product.stock_quantity > 0 ? "InStock" : "OutOfStock"}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      {/* ---- Inspection affordances ----------------------------------- */}
      <nav className="res__tabs" aria-label="Inspect this resource">
        <button className={tab === "triples" ? "is-on" : ""} onClick={() => toggle("triples")}>
          {ownTriples.length} triples
        </button>
        <button className={tab === "graph" ? "is-on" : ""} onClick={() => toggle("graph")}>
          Graph
        </button>
        <button className={tab === "proof" ? "is-on" : ""} onClick={() => toggle("proof")}>
          Why this?
        </button>
        <button className={tab === "reasoning" ? "is-on" : ""} onClick={() => toggle("reasoning")}>
          Reasoning
        </button>
        {onSimilar && mode !== "keyword" && (
          <button onClick={() => onSimilar(product)} title="Products nearest to this one by embedding">
            Similar <Icon name="arrowUpRight" size={12} />
          </button>
        )}
      </nav>

      {tab === "triples" && (
        <div className="res__panel">
          <table className="triples">
            <thead>
              <tr>
                <th>predicate</th>
                <th>object</th>
              </tr>
            </thead>
            <tbody>
              {ownTriples.map((t, i) => (
                <tr key={i}>
                  <td>
                    <Term term={t.p} role="prop" />
                  </td>
                  <td>
                    <Term term={t.o} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="res__panel-note">
            Subject omitted from every row — it is the URI in the header. This is the
            abbreviation Turtle uses too.
          </p>
        </div>
      )}

      {tab === "graph" && (
        <div className="res__panel">
          <ResourceGraph triples={ownTriples} label={product.name} />
        </div>
      )}

      {tab === "proof" && (
        <div className="res__panel">
          <ol className="proof">
            {proof.map((p, i) => (
              <li key={i} className="proof__step">
                <span className="proof__index">{i + 1}</span>
                <div>
                  <div className="proof__what">{p.step}</div>
                  <div className="proof__detail">{p.detail}</div>
                </div>
              </li>
            ))}
          </ol>
          <p className="res__panel-note">
            <strong>Belief:</strong> {trust.basis}
          </p>
          {measured && (
            <p className="res__panel-note">
              <strong>Measured:</strong> {measured.text}. A lower bound — unlabelled good matches count as misses.
            </p>
          )}
        </div>
      )}
      {tab === "reasoning" && (
        <div className="res__panel">
          <Reasoning productId={product.product_id} />
        </div>
      )}
    </article>
  );
}
