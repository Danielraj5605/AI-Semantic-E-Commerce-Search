import { LAYER_CAKE, UNIT_MAP } from "../concepts";
import Icon from "./Icon";

/**
 * The layer cake (Unit 1) drawn as a real stack rather than described in prose.
 *
 * Each layer states what this application actually does at that level, and is
 * marked `full` or `partial` — an honest cake is more instructive than one that
 * claims proof and trust it has not implemented.
 */

export function LayerCakeStack({ compact = false }) {
  return (
    <ol className={`cake ${compact ? "cake--compact" : ""}`}>
      {[...LAYER_CAKE].reverse().map((l, i) => (
        <li key={l.layer} className={`cake__layer cake__layer--${l.state}`} style={{ "--i": i }}>
          <div className="cake__bar">
            <span className="cake__name">{l.layer}</span>
            <span className="cake__role">{l.role}</span>
            <span className={`cake__state cake__state--${l.state}`}>
              {l.state === "full" ? "implemented" : "partial"}
            </span>
          </div>
          {!compact && <p className="cake__here">{l.here}</p>}
        </li>
      ))}
    </ol>
  );
}

export function UnitMap() {
  return (
    <div className="units">
      {UNIT_MAP.map((u) => (
        <article key={u.id} className="unit">
          <header className="unit__head">
            <span className="unit__no">{u.unit}</span>
            <h3 className="unit__title">{u.title}</h3>
          </header>
          <p className="unit__topics">{u.topics}</p>
          <p className="unit__where">
            <span className="unit__where-label">In this app</span>
            {u.surfaces}
          </p>
        </article>
      ))}
    </div>
  );
}

export default function ConceptsDrawer({ open, onClose }) {
  if (!open) return null;

  return (
    <div className="drawer" role="dialog" aria-modal="true" aria-label="Semantic Web concepts">
      <div className="drawer__scrim" onClick={onClose} />
      <div className="drawer__panel">
        <header className="drawer__head">
          <div>
            <h2 className="drawer__title">Where the concepts live</h2>
            <p className="drawer__sub">21CSE452T · Semantic Web — the stack, and this app on it</p>
          </div>
          <button className="drawer__close" onClick={onClose} aria-label="Close">
            <Icon name="close" size={16} />
          </button>
        </header>

        <div className="drawer__body">
          <section className="section">
            <h3 className="section__title">The layer cake</h3>
            <p className="panel__lede">
              Read bottom-up: each layer can only mean something because the one beneath it
              already settled identity, then syntax, then statements, then vocabulary. The
              upper layers are where most working systems stop short, so each one states its
              scope: this reasoner is rule-based (OWL 2 RL style), not a full OWL DL prover.
            </p>
            <LayerCakeStack />
          </section>

          <section className="section">
            <h3 className="section__title">Syllabus map</h3>
            <p className="panel__lede">
              Each unit of the course has a corresponding surface in the interface.
            </p>
            <UnitMap />
          </section>

          <section className="section">
            <h3 className="section__title">The honest caveat</h3>
            <p className="panel__prose">
              Ranking here is done by <em>vector similarity</em>, not by logical entailment.
              That is statistical semantics, not the formal semantics of RDF and OWL — the two
              share a word and very little else. The logic, proof and trust layers apply to
              the catalogue&rsquo;s facts; the match confidence is the one statistical claim,
              and it is measured rather than assumed. What this application shows is the pairing:
              the catalogue is published as a graph with real vocabularies, identity and
              provenance, and the retrieval step is treated as an external service invocation
              (Unit 3) that the graph records the result of. Where a fact is asserted, it says
              so; where it is only believed, it says that instead.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
