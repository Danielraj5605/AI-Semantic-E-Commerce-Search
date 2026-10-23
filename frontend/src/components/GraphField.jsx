import { useEffect, useRef } from "react";

/**
 * The hero background: a live knowledge graph rather than a decorative gradient.
 *
 * Nodes are real terms from this catalogue's vocabulary (classes, properties,
 * resources, typed literals), coloured by the same term-kind convention as every
 * triple table in the app. Edges form between nearby nodes, and a pulse now and
 * then travels along one, the way a query binds across a graph. It drifts
 * slowly, leans gently toward the pointer, pauses when off-screen, and is a still
 * frame for anyone who prefers reduced motion.
 */

const TERMS = [
  ["class", "schema:Product"], ["class", "cat:Electronics"], ["class", "cat:Laptops"],
  ["class", "cat:Footwear"], ["class", "cat:TopRated"], ["class", "cat:Premium"],
  ["class", "owl:Class"], ["class", "schema:Offer"], ["class", "schema:Brand"],
  ["prop", "rdfs:subClassOf"], ["prop", "rdf:type"], ["prop", "schema:offers"],
  ["prop", "prov:wasDerivedFrom"], ["prop", "owl:equivalentClass"],
  ["uri", "ex:product/8f3a"], ["uri", "ex:brand/northline"], ["uri", "ex:table/products"],
  ["uri", "ex:product/c21d"], ["uri", "ex:product/4b90"],
  ["lit", "\"189.00\"^^xsd:decimal"], ["lit", "\"Insulated Parka\"@en"], ["lit", "\"4.6\"^^xsd:decimal"],
  ["bnode", "_:offer"], ["bnode", "_:rating"],
];

const VARS = { uri: "--uri", class: "--class", lit: "--lit", bnode: "--bnode", prop: "--prop" };

function readPalette() {
  const cs = getComputedStyle(document.documentElement);
  const out = {};
  for (const [k, v] of Object.entries(VARS)) out[k] = cs.getPropertyValue(v).trim() || "#888";
  out.line = cs.getPropertyValue("--graph-line").trim() || "rgba(128,128,128,.2)";
  out.accent = cs.getPropertyValue("--accent").trim() || "#f26b3a";
  out.label = cs.getPropertyValue("--ink-3").trim() || "#777";
  return out;
}

export default function GraphField({ density = 1 }) {
  const ref = useRef(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas.getContext("2d");
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let palette = readPalette();
    let w = 0, h = 0, dpr = 1, raf = 0, visible = true, t0 = performance.now();
    const pointer = { x: -1e4, y: -1e4 };
    let nodes = [];
    const pulses = [];

    const seed = () => {
      const count = Math.round(Math.min(46, Math.max(22, (w * h) / 26000)) * density);
      nodes = Array.from({ length: count }, (_, i) => {
        const [kind, label] = TERMS[i % TERMS.length];
        return {
          kind, label,
          x: Math.random() * w, y: Math.random() * h,
          vx: (Math.random() - 0.5) * 0.18, vy: (Math.random() - 0.5) * 0.18,
          r: kind === "class" ? 3.2 : kind === "lit" ? 2.6 : 2.4,
          showLabel: i < TERMS.length && Math.random() < 0.55,
          phase: Math.random() * Math.PI * 2,
        };
      });
    };

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = rect.width; h = rect.height;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      if (!nodes.length) seed();
    };

    const LINK = 150;

    const frame = (now) => {
      const dt = Math.min(48, now - t0);
      t0 = now;
      ctx.clearRect(0, 0, w, h);

      // drift + gentle pull toward the pointer
      for (const n of nodes) {
        if (!reduce) {
          const dx = pointer.x - n.x, dy = pointer.y - n.y;
          const d2 = dx * dx + dy * dy;
          if (d2 < 220 * 220) {
            const f = 0.00002 * (1 - Math.sqrt(d2) / 220);
            n.vx += dx * f; n.vy += dy * f;
          }
          n.vx *= 0.995; n.vy *= 0.995;
          const speed = Math.hypot(n.vx, n.vy);
          if (speed < 0.05) { n.vx += (Math.random() - 0.5) * 0.02; n.vy += (Math.random() - 0.5) * 0.02; }
          n.x += n.vx * dt * 0.06;
          n.y += n.vy * dt * 0.06;
          if (n.x < -20) n.x = w + 20; if (n.x > w + 20) n.x = -20;
          if (n.y < -20) n.y = h + 20; if (n.y > h + 20) n.y = -20;
        }
      }

      // edges
      const edges = [];
      ctx.lineWidth = 1;
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i], b = nodes[j];
          const d = Math.hypot(a.x - b.x, a.y - b.y);
          if (d < LINK) {
            edges.push([a, b]);
            ctx.globalAlpha = (1 - d / LINK) * 0.9;
            ctx.strokeStyle = palette.line;
            ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
          }
        }
      }

      // pulses: a binding travelling along an edge
      if (!reduce && edges.length && Math.random() < 0.035 && pulses.length < 5) {
        const [a, b] = edges[(Math.random() * edges.length) | 0];
        pulses.push({ a, b, p: 0 });
      }
      for (let i = pulses.length - 1; i >= 0; i--) {
        const q = pulses[i];
        q.p += dt / 900;
        if (q.p >= 1) { pulses.splice(i, 1); continue; }
        const x = q.a.x + (q.b.x - q.a.x) * q.p, y = q.a.y + (q.b.y - q.a.y) * q.p;
        ctx.globalAlpha = Math.sin(q.p * Math.PI);
        ctx.fillStyle = palette.accent;
        ctx.beginPath(); ctx.arc(x, y, 2.2, 0, Math.PI * 2); ctx.fill();
        ctx.globalAlpha = Math.sin(q.p * Math.PI) * 0.25;
        ctx.beginPath(); ctx.arc(x, y, 7, 0, Math.PI * 2); ctx.fill();
      }

      // nodes and labels
      ctx.font = "500 10.5px 'Geist Mono', ui-monospace, monospace";
      for (const n of nodes) {
        const breathe = reduce ? 1 : 0.85 + Math.sin(now / 1400 + n.phase) * 0.15;
        ctx.globalAlpha = 0.95 * breathe;
        ctx.fillStyle = palette[n.kind];
        ctx.beginPath();
        if (n.kind === "lit") ctx.rect(n.x - n.r, n.y - n.r, n.r * 2, n.r * 2);
        else ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        ctx.fill();
        if (n.showLabel) {
          ctx.globalAlpha = 0.5 * breathe;
          ctx.fillStyle = palette.label;
          ctx.fillText(n.label, n.x + 8, n.y + 3.5);
        }
      }
      ctx.globalAlpha = 1;

      if (!reduce && visible) raf = requestAnimationFrame(frame);
    };

    resize();
    frame(performance.now());

    const ro = new ResizeObserver(() => { resize(); if (reduce) frame(performance.now()); });
    ro.observe(canvas);

    const io = new IntersectionObserver(([e]) => {
      const was = visible;
      visible = e.isIntersecting && !document.hidden;
      if (visible && !was && !reduce) { t0 = performance.now(); raf = requestAnimationFrame(frame); }
    });
    io.observe(canvas);

    const onVis = () => {
      const was = visible;
      visible = !document.hidden;
      if (visible && !was && !reduce) { t0 = performance.now(); raf = requestAnimationFrame(frame); }
    };
    document.addEventListener("visibilitychange", onVis);

    const onMove = (e) => {
      const r = canvas.getBoundingClientRect();
      pointer.x = e.clientX - r.left; pointer.y = e.clientY - r.top;
    };
    const onLeave = () => { pointer.x = pointer.y = -1e4; };
    window.addEventListener("pointermove", onMove, { passive: true });
    window.addEventListener("pointerleave", onLeave);

    // repaint in the new palette when the theme flips
    const mo = new MutationObserver(() => { palette = readPalette(); if (reduce) frame(performance.now()); });
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect(); io.disconnect(); mo.disconnect();
      document.removeEventListener("visibilitychange", onVis);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerleave", onLeave);
    };
  }, [density]);

  return <canvas ref={ref} className="graphfield" aria-hidden="true" />;
}
