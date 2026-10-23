import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY } from "d3-force";
import { categoryURI } from "../rdf";
import Icon from "./Icon";

/**
 * The answer as a graph you can move through.
 *
 * Nodes are the things the answer is made of: the ?query binding, the classes
 * the products are typed with (and their superclasses, joined by
 * rdfs:subClassOf), and the products themselves. A product's distance from the
 * query is driven by its similarity score, so the closest thing on screen is the
 * best match. Hover to see a node's neighbourhood, click a product to inspect it,
 * click a class to narrow the answer to it. Pan by dragging the canvas, zoom
 * with the wheel or the buttons, drag a node to pull it about.
 */

const truncate = (s, n) => (s && s.length > n ? `${s.slice(0, n - 1)}…` : s || "");
const money = (v) => (v == null ? "" : `$${Number(v).toFixed(2)}`);

function buildGraph(results, categories, mode) {
  const byName = new Map((categories || []).map((c) => [c.name, c]));
  const byId = new Map((categories || []).map((c) => [c.category_id, c]));
  const nodes = [{ id: "q", kind: "query", fx: 0, fy: 0 }];
  const links = [];
  const classIds = new Set();

  const addClass = (name) => {
    const id = `c:${name}`;
    if (classIds.has(id)) return id;
    classIds.add(id);
    nodes.push({ id, kind: "class", name, qname: categoryURI(name) });
    const parent = byId.get(byName.get(name)?.parent_category_id);
    if (parent && parent.name !== name) {
      const pid = addClass(parent.name);
      links.push({ source: id, target: pid, kind: "subclass" });
    } else {
      links.push({ source: id, target: "q", kind: "bind" });
    }
    return id;
  };

  results.slice(0, 40).forEach((r, i) => {
    const p = r.product;
    const score = mode === "semantic" && r.score != null ? r.score : null;
    const rank = i + 1;
    nodes.push({
      id: p.product_id,
      kind: "product",
      product: p,
      result: r,
      score,
      rank,
      radius: score != null ? 15 + Math.max(0, Math.min(1, score / 0.7)) * 17 : 21 - Math.min(i, 8),
    });
    if (p.category_name) {
      links.push({ source: p.product_id, target: addClass(p.category_name), kind: "type" });
    }
    links.push({ source: "q", target: p.product_id, kind: "similarity", score, rank });
  });

  return { nodes, links };
}

export default function GraphExplorer({ results, query, mode, categories, selectedId, onSelect, onClassClick, seedName }) {
  const wrapRef = useRef(null);
  const simRef = useRef(null);
  const [size, setSize] = useState({ w: 800, h: 600 });
  const [, setTick] = useState(0);
  const [view, setView] = useState({ x: 0, y: 0, k: 1 });
  const [hover, setHover] = useState(null);
  const fitted = useRef(false);
  const viewRef = useRef(view);
  viewRef.current = view;
  // fit() runs from simulation callbacks created on an earlier render, so it
  // must read the current size through a ref, not a stale closure
  const sizeRef = useRef(size);
  sizeRef.current = size;

  const graph = useMemo(() => buildGraph(results, categories, mode), [results, categories, mode]);

  // neighbourhood for highlighting
  const neighbours = useMemo(() => {
    const m = new Map();
    graph.links.forEach((l) => {
      const s = typeof l.source === "object" ? l.source.id : l.source;
      const t = typeof l.target === "object" ? l.target.id : l.target;
      if (l.kind === "similarity") return;
      if (!m.has(s)) m.set(s, new Set());
      if (!m.has(t)) m.set(t, new Set());
      m.get(s).add(t);
      m.get(t).add(s);
    });
    return m;
  }, [graph]);

  // keep the canvas sized to its container
  useEffect(() => {
    const el = wrapRef.current;
    const ro = new ResizeObserver(([e]) => setSize({ w: e.contentRect.width, h: e.contentRect.height }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const fit = useCallback(
    (animate = true) => {
      const ns = graph.nodes;
      if (!ns.length) return;
      let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
      ns.forEach((n) => {
        const r = (n.radius || 30) + 40;
        x0 = Math.min(x0, n.x - r); x1 = Math.max(x1, n.x + r);
        y0 = Math.min(y0, n.y - r); y1 = Math.max(y1, n.y + r);
      });
      const { w, h } = sizeRef.current;
      const pad = w < 600 ? 12 : 60;
      const k = Math.min(1.8, Math.max(0.2, Math.min((w - pad * 2) / (x1 - x0), (h - pad * 2) / (y1 - y0))));
      const target = { k, x: -((x0 + x1) / 2) * k, y: -((y0 + y1) / 2) * k };
      if (!animate || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        setView(target);
        return;
      }
      const from = viewRef.current;
      const start = performance.now();
      const step = (now) => {
        const p = Math.min(1, (now - start) / 700);
        const e = 1 - Math.pow(1 - p, 3);
        setView({ k: from.k + (target.k - from.k) * e, x: from.x + (target.x - from.x) * e, y: from.y + (target.y - from.y) * e });
        if (p < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    },
    [graph]
  );

  // the simulation
  useEffect(() => {
    fitted.current = false;
    const sim = forceSimulation(graph.nodes)
      .force(
        "link",
        forceLink(graph.links)
          .id((d) => d.id)
          .distance((l) =>
            l.kind === "similarity" ? 150 + (l.score != null ? (1 - Math.min(1, l.score / 0.7)) * 230 : l.rank * 14)
              : l.kind === "type" ? 78
              : l.kind === "subclass" ? 96
              : 150
          )
          .strength((l) => (l.kind === "similarity" ? 0.12 : l.kind === "bind" ? 0.25 : 0.7))
      )
      .force("charge", forceManyBody().strength((d) => (d.kind === "product" ? -360 : d.kind === "class" ? -420 : -600)))
      .force(
        "collide",
        forceCollide()
          .radius((d) => (d.kind === "product" ? d.radius + 26 : d.kind === "class" ? d.qname.length * 3.4 + 16 : 48))
          .strength(0.9)
      )
      .force("x", forceX(0).strength(0.03))
      .force("y", forceY(0).strength(0.04))
      .alphaDecay(0.035);

    sim.on("tick", () => setTick((t) => t + 1));
    sim.on("end", () => {
      if (!fitted.current) {
        fitted.current = true;
        fit(true);
      }
    });
    simRef.current = sim;
    // an early fit so the first frames are framed, refined when the layout settles
    const early = setTimeout(() => fit(false), 60);
    const settle = setTimeout(() => fit(true), 900);
    return () => {
      clearTimeout(early);
      clearTimeout(settle);
      sim.stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph]);

  /* ---- pan, zoom, drag ------------------------------------------------- */
  const drag = useRef(null);

  const toWorld = (cx, cy) => {
    const rect = wrapRef.current.getBoundingClientRect();
    const v = viewRef.current;
    return { x: (cx - rect.left - size.w / 2 - v.x) / v.k, y: (cy - rect.top - size.h / 2 - v.y) / v.k };
  };

  const onWheel = (e) => {
    e.preventDefault();
    const rect = wrapRef.current.getBoundingClientRect();
    const mx = e.clientX - rect.left - size.w / 2;
    const my = e.clientY - rect.top - size.h / 2;
    setView((v) => {
      const k = Math.min(3, Math.max(0.25, v.k * Math.exp(-e.deltaY * 0.0015)));
      const f = k / v.k;
      return { k, x: mx - (mx - v.x) * f, y: my - (my - v.y) * f };
    });
  };

  // wheel must be non-passive to stop the page scrolling
  useEffect(() => {
    const el = wrapRef.current;
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  });

  const onPointerDown = (e, node = null) => {
    e.stopPropagation();
    e.currentTarget.setPointerCapture?.(e.pointerId);
    if (node && node.kind !== "query") {
      drag.current = { node, moved: false, sx: e.clientX, sy: e.clientY };
      simRef.current.alphaTarget(0.25).restart();
    } else {
      drag.current = { pan: true, sx: e.clientX, sy: e.clientY, vx: viewRef.current.x, vy: viewRef.current.y };
    }
  };

  const onPointerMove = (e) => {
    const d = drag.current;
    if (!d) return;
    if (Math.abs(e.clientX - d.sx) + Math.abs(e.clientY - d.sy) > 4) d.moved = true;
    if (d.pan) {
      setView((v) => ({ ...v, x: d.vx + (e.clientX - d.sx), y: d.vy + (e.clientY - d.sy) }));
    } else {
      const w = toWorld(e.clientX, e.clientY);
      d.node.fx = w.x;
      d.node.fy = w.y;
    }
  };

  const onPointerUp = () => {
    const d = drag.current;
    drag.current = null;
    if (!d || d.pan) return;
    simRef.current.alphaTarget(0);
    d.node.fx = null;
    d.node.fy = null;
    if (!d.moved) activate(d.node);
  };

  const activate = (node) => {
    if (node.kind === "product") onSelect(node.product.product_id === selectedId ? null : node.product);
    else if (node.kind === "class") onClassClick?.(node.name);
  };

  const zoomBy = (f) =>
    setView((v) => {
      const k = Math.min(3, Math.max(0.25, v.k * f));
      return { k, x: v.x * (k / v.k), y: v.y * (k / v.k) };
    });

  /* ---- render ----------------------------------------------------------- */
  const focus = hover || selectedId;
  const lit = focus ? new Set([focus, ...(neighbours.get(focus) || [])]) : null;
  const isLit = (id) => !lit || lit.has(id);
  const tx = size.w / 2 + view.x;
  const ty = size.h / 2 + view.y;

  const hovered = hover ? graph.nodes.find((n) => n.id === hover) : null;
  const showLabels = view.k > 0.7;

  return (
    <div
      ref={wrapRef}
      className="gx"
      onPointerDown={(e) => onPointerDown(e)}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerLeave={onPointerUp}
      onDoubleClick={() => fit(true)}
    >
      <svg className="gx__svg" width={size.w} height={size.h} role="img" aria-label={`Knowledge graph of ${results.length} results`}>
        <defs>
          <pattern id="gx-dots" width="28" height="28" patternUnits="userSpaceOnUse" patternTransform={`translate(${tx % 28} ${ty % 28}) scale(${view.k})`}>
            <circle cx="1" cy="1" r="1" className="gx__dot" />
          </pattern>
          {graph.nodes
            .filter((n) => n.kind === "product")
            .map((n) => (
              <clipPath key={n.id} id={`clip-${n.id}`}>
                <circle r={n.radius} />
              </clipPath>
            ))}
        </defs>
        <rect width={size.w} height={size.h} fill="url(#gx-dots)" />

        <g transform={`translate(${tx} ${ty}) scale(${view.k})`}>
          {/* edges */}
          {graph.links.map((l, i) => {
            const s = l.source, t = l.target;
            if (s.x == null || t.x == null) return null;
            const on = focus && (s.id === focus || t.id === focus);
            const dim = focus && !on;
            const label =
              l.kind === "type" ? "rdf:type" : l.kind === "subclass" ? "rdfs:subClassOf" : l.kind === "bind" ? "" : l.score != null ? `cat:similarityScore ${l.score.toFixed(3)}` : `rank ${l.rank}`;
            return (
              <g key={i} className={`gx__edge gx__edge--${l.kind} ${on ? "is-on" : ""} ${dim ? "is-dim" : ""}`}>
                <line x1={s.x} y1={s.y} x2={t.x} y2={t.y} style={l.kind === "similarity" && l.score != null ? { "--w": l.score } : undefined} />
                {on && label && (
                  <text x={(s.x + t.x) / 2} y={(s.y + t.y) / 2 - 6} textAnchor="middle" className="gx__elabel">
                    {label}
                  </text>
                )}
              </g>
            );
          })}

          {/* nodes */}
          {graph.nodes.map((n, i) => {
            if (n.x == null) return null;
            const dim = !isLit(n.id);
            const common = {
              transform: `translate(${n.x} ${n.y})`,
              onPointerDown: (e) => onPointerDown(e, n),
              onPointerEnter: () => setHover(n.id),
              onPointerLeave: () => setHover((h) => (h === n.id ? null : h)),
              style: { "--i": Math.min(i, 30) },
            };

            if (n.kind === "query") {
              return (
                <g key={n.id} {...common} className={`gx__node gx__node--query ${dim ? "is-dim" : ""}`}>
                  <circle className="gx__ring" r="26" />
                  <circle className="gx__ring gx__ring--2" r="26" />
                  <circle r="22" className="gx__core" />
                  <text className="gx__qvar" y="4" textAnchor="middle">?q</text>
                  <text className="gx__qlabel" y="46" textAnchor="middle">
                    {seedName ? `nearest to “${truncate(seedName, 30)}”` : `“${truncate(query, 36)}”`}
                  </text>
                </g>
              );
            }

            if (n.kind === "class") {
              const w = Math.max(70, n.qname.length * 6.6 + 22);
              return (
                <g
                  key={n.id}
                  {...common}
                  className={`gx__node gx__node--class ${dim ? "is-dim" : ""}`}
                  tabIndex={0}
                  role="button"
                  aria-label={`Class ${n.qname}. Narrow the answer to it.`}
                  onKeyDown={(e) => e.key === "Enter" && activate(n)}
                >
                  <rect x={-w / 2} y={-13} width={w} height={26} rx={13} />
                  <text y="4" textAnchor="middle">{n.qname}</text>
                </g>
              );
            }

            const p = n.product;
            const selected = p.product_id === selectedId;
            return (
              <g
                key={n.id}
                {...common}
                className={`gx__node gx__node--product ${dim ? "is-dim" : ""} ${selected ? "is-selected" : ""}`}
                tabIndex={0}
                role="button"
                aria-label={`${p.name}${n.score != null ? `, similarity ${n.score.toFixed(3)}` : ""}. Inspect.`}
                onKeyDown={(e) => e.key === "Enter" && activate(n)}
              >
                <circle r={n.radius + 5} className="gx__halo" />
                <circle r={n.radius} className="gx__disc" />
                {p.image_url && (
                  <image
                    href={p.image_url}
                    x={-n.radius}
                    y={-n.radius}
                    width={n.radius * 2}
                    height={n.radius * 2}
                    preserveAspectRatio="xMidYMid slice"
                    clipPath={`url(#clip-${n.id})`}
                  />
                )}
                <circle r={n.radius} className="gx__rim" />
                <g transform={`translate(${n.radius * 0.72} ${-n.radius * 0.72})`} className="gx__rank">
                  <circle r="9" />
                  <text y="3.5" textAnchor="middle">{n.rank}</text>
                </g>
                {(showLabels || selected || hover === n.id) && (
                  <text y={n.radius + 16} textAnchor="middle" className="gx__plabel">
                    {truncate(p.name, 24)}
                  </text>
                )}
              </g>
            );
          })}
        </g>
      </svg>

      {/* hover card */}
      {hovered && hovered.kind === "product" && !drag.current && (
        <div
          className="gx__tip"
          style={{
            left: tx + hovered.x * view.k,
            top: ty + (hovered.y - hovered.radius) * view.k - 12,
          }}
        >
          <div className="gx__tip-name">{hovered.product.name}</div>
          <div className="gx__tip-meta">
            <span className="term term--class">{categoryURI(hovered.product.category_name || "Thing")}</span>
            <span>{money(hovered.product.price)}</span>
            {hovered.score != null && <span className="gx__tip-score">{hovered.score.toFixed(3)}</span>}
          </div>
          <div className="gx__tip-hint">Click to inspect</div>
        </div>
      )}
      {hovered && hovered.kind === "class" && (
        <div className="gx__tip" style={{ left: tx + hovered.x * view.k, top: ty + hovered.y * view.k - 22 }}>
          <div className="gx__tip-name">{hovered.name}</div>
          <div className="gx__tip-hint">owl:Class · click to narrow the answer to it</div>
        </div>
      )}

      {/* controls */}
      <div className="gx__zoom" onPointerDown={(e) => e.stopPropagation()}>
        <button onClick={() => zoomBy(1.25)} aria-label="Zoom in">+</button>
        <button onClick={() => zoomBy(0.8)} aria-label="Zoom out">−</button>
        <button onClick={() => fit(true)} aria-label="Fit the graph to the screen" title="Fit">
          <Icon name="graph" size={14} />
        </button>
      </div>

      <ul className="gx__legend" onPointerDown={(e) => e.stopPropagation()}>
        <li><span className="gx__lg gx__lg--query" /> ?query</li>
        <li><span className="gx__lg gx__lg--class" /> owl:Class</li>
        <li><span className="gx__lg gx__lg--product" /> schema:Product</li>
        <li><span className="gx__lg gx__lg--sim" /> closer = more similar</li>
      </ul>
    </div>
  );
}
