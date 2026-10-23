import { useMemo } from "react";
import { categoryURI } from "../rdf";

/**
 * RDF visualisation (Unit 1: "Describing Data with RDF — properties,
 * visualisation").
 *
 * Two views, both plain inline SVG so they inherit the page theme and stay
 * crisp at any zoom:
 *
 *   ResourceGraph — the star of triples around one subject.
 *   ResultGraph   — the whole answer set, clustered by the class each
 *                   product is entailed to belong to.
 */

const truncate = (s, n) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

/** Colour role per term kind — the same convention used in the triple tables. */
const roleOf = (term) => {
  if (term.term === "literal") return "lit";
  if (term.term === "bnode") return "bnode";
  if (term.value.startsWith("cat:") || term.value.startsWith("schema:")) return "class";
  return "uri";
};

// Kept short deliberately: these sit at the rim of the viewBox, and a label
// that runs off the edge is worse than one that is elided.
const labelOf = (term) => {
  if (term.term === "literal") return truncate(term.value, 18);
  if (term.term === "bnode") return `_:${term.value.split("-")[0]}`;
  if (term.value.startsWith("http")) return truncate(term.value.replace(/^https?:\/\//, ""), 20);
  return truncate(term.value, 21);
};

/* ============================================================
   ONE SUBJECT, MANY PROPERTIES
   ============================================================ */

export function ResourceGraph({ triples, label }) {
  const W = 760;
  const H = 460;
  const cx = W / 2;
  const cy = H / 2;

  const spokes = useMemo(() => {
    // Only the triples whose subject is the resource itself; blank-node
    // sub-trees are summarised by their type rather than drawn twice.
    const n = triples.length;
    const rx = 232;
    const ry = 162;
    return triples.map((t, i) => {
      const angle = (i / n) * Math.PI * 2 - Math.PI / 2;
      const cos = Math.cos(angle);
      const x = cx + cos * rx;
      const y = cy + Math.sin(angle) * ry;
      // Near-vertical spokes have nowhere to put a side label without sitting
      // on top of their own node, so those labels go above or below instead.
      const vertical = Math.abs(cos) <= 0.15;
      return {
        t,
        x,
        y,
        anchor: vertical ? "middle" : cos > 0 ? "start" : "end",
        dx: vertical ? 0 : cos > 0 ? 12 : -12,
        dy: vertical ? (y < cy ? -15 : 21) : 4,
      };
    });
  }, [triples, cx, cy]);

  if (!triples.length) return <p className="graph__empty">No statements to draw.</p>;

  return (
    <div className="graph">
      <svg viewBox={`0 0 ${W} ${H}`} className="graph__svg" role="img" aria-label={`RDF graph of ${label}`}>
        {spokes.map(({ t, x, y }, i) => {
          // Predicate labels sit past the midpoint rather than on it: spokes
          // fan out from the centre, so there is more room between them the
          // further along the edge you go.
          const f = 0.62;
          const mx = cx + (x - cx) * f;
          const my = cy + (y - cy) * f;
          return (
            <g key={`edge-${i}`} className="graph__edge">
              <line x1={cx} y1={cy} x2={x} y2={y} />
              <text x={mx} y={my - 5} className="graph__plabel" textAnchor="middle">
                {t.p.value}
              </text>
            </g>
          );
        })}

        {spokes.map(({ t, x, y, anchor, dx, dy }, i) => (
          <g key={`node-${i}`} className={`graph__node graph__node--${roleOf(t.o)}`}>
            {t.o.term === "literal" ? (
              <rect x={x - 7} y={y - 7} width={14} height={14} rx={2} />
            ) : (
              <circle cx={x} cy={y} r={8} />
            )}
            <text x={x + dx} y={y + dy} textAnchor={anchor} className="graph__olabel">
              {labelOf(t.o)}
            </text>
          </g>
        ))}

        <g className="graph__node graph__node--subject">
          <circle cx={cx} cy={cy} r={15} />
          <text x={cx} y={cy + 38} textAnchor="middle" className="graph__slabel">
            {truncate(label, 42)}
          </text>
        </g>
      </svg>

      <Legend />
    </div>
  );
}

/* ============================================================
   THE WHOLE ANSWER, CLUSTERED BY CLASS
   ============================================================ */

export function ResultGraph({ results, query }) {
  const W = 900;
  const H = 560;
  const cx = W / 2;
  const cy = H / 2;

  const { classNodes, productNodes } = useMemo(() => {
    const byClass = new Map();
    for (const r of results.slice(0, 24)) {
      const key = r.product.category_name || "Uncategorised";
      if (!byClass.has(key)) byClass.set(key, []);
      byClass.get(key).push(r);
    }

    const classes = [...byClass.entries()];
    const cNodes = [];
    const pNodes = [];

    // A half-step rotation keeps the classes off the exact vertical and
    // horizontal axes, which otherwise reads as a plus sign rather than a graph.
    const rot = -Math.PI / 2 + Math.PI / classes.length;

    classes.forEach(([name, members], ci) => {
      const base = (ci / classes.length) * Math.PI * 2 + rot;
      cNodes.push({
        name,
        qname: categoryURI(name),
        x: cx + Math.cos(base) * 152,
        y: cy + Math.sin(base) * 116,
        count: members.length,
      });

      const spread = Math.min(Math.PI / classes.length, 0.6);
      members.forEach((r, mi) => {
        const offset = members.length === 1 ? 0 : (mi / (members.length - 1) - 0.5) * spread * 2;
        const a = base + offset;
        const cos = Math.cos(a);
        pNodes.push({
          r,
          classIndex: ci,
          x: cx + cos * 300,
          y: cy + Math.sin(a) * 214,
          anchor: cos > 0.12 ? "start" : cos < -0.12 ? "end" : "middle",
          dx: cos > 0.12 ? 12 : cos < -0.12 ? -12 : 0,
        });
      });
    });

    return { classNodes: cNodes, productNodes: pNodes };
  }, [results, cx, cy]);

  if (!results.length) return <p className="graph__empty">Nothing to draw yet.</p>;

  return (
    <div className="graph">
      <svg viewBox={`0 0 ${W} ${H}`} className="graph__svg" role="img" aria-label="Graph of the answer set">
        {classNodes.map((c, i) => (
          <line key={`ce-${i}`} className="graph__edge-line" x1={cx} y1={cy} x2={c.x} y2={c.y} />
        ))}
        {productNodes.map((p, i) => {
          const c = classNodes[p.classIndex];
          return (
            <line key={`pe-${i}`} className="graph__edge-line graph__edge-line--soft" x1={c.x} y1={c.y} x2={p.x} y2={p.y} />
          );
        })}

        {productNodes.map((p, i) => (
          <g key={`pn-${i}`} className="graph__node graph__node--uri">
            <circle cx={p.x} cy={p.y} r={4 + (p.r.score ?? 0.4) * 8} />
            {/* Labels only while they can still be read; past that the tooltip
                carries the name and the shape carries the score. */}
            {productNodes.length <= 14 && (
              <text
                x={p.x + p.dx}
                y={p.y + (p.anchor === "middle" ? (p.y < cy ? -16 : 22) : 4)}
                textAnchor={p.anchor}
                className="graph__plabel graph__plabel--node"
              >
                {truncate(p.r.product.name, 22)}
              </text>
            )}
            <title>
              {p.r.product.name}
              {p.r.score != null ? ` — cat:similarityScore ${p.r.score.toFixed(3)}` : ""}
            </title>
          </g>
        ))}

        {classNodes.map((c, i) => (
          <g key={`cn-${i}`} className="graph__node graph__node--class">
            <circle cx={c.x} cy={c.y} r={9} />
            <text x={c.x} y={c.y - 16} textAnchor="middle" className="graph__olabel">
              {truncate(c.qname, 22)}
            </text>
          </g>
        ))}

        <g className="graph__node graph__node--query">
          <circle cx={cx} cy={cy} r={17} />
          <text x={cx} y={cy + 40} textAnchor="middle" className="graph__slabel">
            ?query “{truncate(query, 34)}”
          </text>
        </g>
      </svg>

      <p className="graph__caption">
        Node size encodes <code>cat:similarityScore</code>. Edges from the centre are the
        service binding; edges from a class are <code>rdf:type</code> assertions.
      </p>
      <Legend />
    </div>
  );
}

function Legend() {
  return (
    <ul className="legend">
      <li>
        <span className="legend__dot legend__dot--uri" /> resource (URI)
      </li>
      <li>
        <span className="legend__dot legend__dot--class" /> class
      </li>
      <li>
        <span className="legend__dot legend__dot--lit legend__dot--square" /> literal
      </li>
      <li>
        <span className="legend__dot legend__dot--bnode" /> blank node
      </li>
    </ul>
  );
}
