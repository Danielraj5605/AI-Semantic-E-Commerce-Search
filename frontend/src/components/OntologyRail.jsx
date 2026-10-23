import { useMemo, useState } from "react";
import { buildClassTree, ontologyAxioms, brandURI } from "../rdf";

/**
 * The left rail is an ontology browser rather than a filter sidebar.
 *
 * Unit 2 asks for the structure of an ontology to be legible: classes, their
 * subsumption relations, and the QName each one is actually known by. Selecting
 * a class narrows the result set — so browsing the ontology and filtering the
 * results are the same gesture, which is the point being made.
 */

function ClassNode({ node, depth, selected, onSelect }) {
  // Open two levels by default: a taxonomy that shows no subclass on arrival
  // fails to demonstrate the one relation it exists to demonstrate.
  const [open, setOpen] = useState(depth < 2);
  const hasChildren = node.children.length > 0;
  const isSelected = selected === node.name;

  return (
    <li className="tree__item">
      <div className="tree__row" style={{ "--depth": depth }}>
        {hasChildren ? (
          <button
            className={`tree__twisty ${open ? "is-open" : ""}`}
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? `Collapse ${node.name}` : `Expand ${node.name}`}
          >
            ▸
          </button>
        ) : (
          <span className="tree__twisty tree__twisty--leaf" aria-hidden="true" />
        )}

        <button
          className={`tree__label ${isSelected ? "is-selected" : ""}`}
          onClick={() => onSelect(isSelected ? null : node.name)}
          title={`${node.qname} rdfs:subClassOf cat:CatalogueThing`}
        >
          <span className="tree__name">{node.name}</span>
          <span className="term term--class">{node.qname}</span>
        </button>
      </div>

      {hasChildren && open && (
        <ul className="tree__children">
          {node.children.map((child) => (
            <ClassNode
              key={child.category_id}
              node={child}
              depth={depth + 1}
              selected={selected}
              onSelect={onSelect}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

export default function OntologyRail({ filters, active, onChange, onClear, onShowAxioms }) {
  const classTree = useMemo(() => buildClassTree(filters?.categories || []), [filters]);
  const axiomCount = useMemo(() => ontologyAxioms(classTree).length, [classTree]);
  const [brandsExpanded, setBrandsExpanded] = useState(false);
  // On a narrow screen the rail sits above the results, so leaving it open
  // would bury the answer under the ontology. Collapsed by default there;
  // the CSS ignores this state entirely at desktop widths.
  const [mobileOpen, setMobileOpen] = useState(false);

  if (!filters) {
    return (
      <aside className="rail">
        <div className="rail__loading">Loading ontology…</div>
      </aside>
    );
  }

  const brands = filters.brands || [];
  const visibleBrands = brandsExpanded ? brands : brands.slice(0, 8);
  const activeCount = Object.keys(active).filter((k) => k !== "limit").length;

  return (
    <aside className="rail" aria-label="Ontology browser">
      <button
        className="rail__disclosure"
        aria-expanded={mobileOpen}
        onClick={() => setMobileOpen((v) => !v)}
      >
        <span>
          Ontology &amp; constraints
          {activeCount > 0 && <span className="rail__badge">{activeCount}</span>}
        </span>
        <span className={`rail__chevron ${mobileOpen ? "is-open" : ""}`} aria-hidden="true">
          ▸
        </span>
      </button>

      <div className={`rail__body ${mobileOpen ? "is-open" : ""}`}>
      {/* ---- Classes -------------------------------------------------- */}
      <section className="rail__section">
        <header className="rail__head">
          <h2 className="rail__title">Classes</h2>
          <span className="rail__note">owl:Class</span>
        </header>
        <p className="rail__blurb">
          Catalogue categories published as a class hierarchy. Selecting one adds a{" "}
          <code>schema:category</code> pattern to the query.
        </p>

        <ul className="tree" role="tree">
          <li className="tree__item">
            <div className="tree__row" style={{ "--depth": 0 }}>
              <span className="tree__twisty tree__twisty--leaf" aria-hidden="true" />
              <button
                className={`tree__label ${!active.category ? "is-selected" : ""}`}
                onClick={() => onChange("category", null)}
              >
                <span className="tree__name">Anything in the catalogue</span>
                <span className="term term--class">cat:CatalogueThing</span>
              </button>
            </div>
            <ul className="tree__children">
              {classTree.map((node) => (
                <ClassNode
                  key={node.category_id}
                  node={node}
                  depth={1}
                  selected={active.category}
                  onSelect={(name) => onChange("category", name)}
                />
              ))}
            </ul>
          </li>
        </ul>

        <button className="rail__link" onClick={onShowAxioms}>
          Inspect {axiomCount} axioms →
        </button>
      </section>

      {/* ---- Brands as instances -------------------------------------- */}
      {brands.length > 0 && (
        <section className="rail__section">
          <header className="rail__head">
            <h2 className="rail__title">Brands</h2>
            <span className="rail__note">schema:Brand</span>
          </header>
          <p className="rail__blurb">
            Individuals, not classes — each is a resource in the <code>ex:</code> namespace.
          </p>
          <div className="chips">
            <button
              className={`chip ${!active.brand ? "is-on" : ""}`}
              onClick={() => onChange("brand", null)}
            >
              any
            </button>
            {visibleBrands.map((b) => (
              <button
                key={b}
                className={`chip ${active.brand === b ? "is-on" : ""}`}
                onClick={() => onChange("brand", active.brand === b ? null : b)}
                title={brandURI(b)}
              >
                {b}
              </button>
            ))}
          </div>
          {brands.length > 8 && (
            <button className="rail__link" onClick={() => setBrandsExpanded((v) => !v)}>
              {brandsExpanded ? "Show fewer" : `Show all ${brands.length}`}
            </button>
          )}
        </section>
      )}

      {/* ---- Datatype constraints ------------------------------------- */}
      <section className="rail__section">
        <header className="rail__head">
          <h2 className="rail__title">Constraints</h2>
          <span className="rail__note">FILTER</span>
        </header>
        <p className="rail__blurb">
          Bounds on typed literals — these become SPARQL <code>FILTER</code> clauses verbatim.
        </p>

        <label className="field">
          <span className="field__label">
            schema:price <span className="term term--lit">xsd:decimal</span>
          </span>
          <div className="field__pair">
            <input
              type="number"
              className="field__input"
              placeholder={`≥ ${Math.floor(filters.price_range?.min ?? 0)}`}
              value={active.min_price ?? ""}
              onChange={(e) => onChange("min_price", e.target.value || null)}
            />
            <span className="field__sep">…</span>
            <input
              type="number"
              className="field__input"
              placeholder={`≤ ${Math.ceil(filters.price_range?.max ?? 1000)}`}
              value={active.max_price ?? ""}
              onChange={(e) => onChange("max_price", e.target.value || null)}
            />
          </div>
        </label>

        <label className="field">
          <span className="field__label">
            schema:ratingValue <span className="term term--lit">xsd:decimal</span>
          </span>
          <div className="field__ratings">
            {[0, 3, 4, 4.5].map((r) => (
              <button
                key={r}
                className={`chip ${Number(active.min_rating ?? 0) === r ? "is-on" : ""}`}
                onClick={() => onChange("min_rating", r === 0 ? null : r)}
              >
                {r === 0 ? "any" : `≥ ${r}`}
              </button>
            ))}
          </div>
        </label>
      </section>

        {activeCount > 0 && (
          <button className="rail__reset" onClick={onClear}>
            Drop {activeCount} constraint{activeCount === 1 ? "" : "s"}
          </button>
        )}
      </div>
    </aside>
  );
}
