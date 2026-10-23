/**
 * One RDF term, coloured by what it *is* rather than by where it sits.
 *
 * The convention is consistent everywhere terms appear — triple tables, graph
 * nodes, the rail, the serialisation panes — so that after a minute of use the
 * colour alone tells you whether you are looking at a resource, a class, a
 * literal or a blank node. That is the whole readability argument for RDF
 * tooling, and it costs nothing to honour it here.
 */

const kindOf = (term) => {
  if (term.term === "literal") return "lit";
  if (term.term === "bnode") return "bnode";
  if (term.value === "rdf:type") return "prop";
  if (term.value.startsWith("cat:") && /^cat:[A-Z]/.test(term.value)) return "class";
  if (term.value.startsWith("schema:") && /^schema:[A-Z]/.test(term.value)) return "class";
  return "uri";
};

export default function Term({ term, role }) {
  const kind = role || kindOf(term);

  if (term.term === "literal") {
    return (
      <span className="term term--lit" title={term.datatype || term.lang || "plain literal"}>
        <span className="term__quote">&ldquo;</span>
        {term.value}
        <span className="term__quote">&rdquo;</span>
        {term.datatype && <span className="term__dt">^^{term.datatype}</span>}
        {!term.datatype && term.lang && <span className="term__dt">@{term.lang}</span>}
      </span>
    );
  }

  if (term.term === "bnode") {
    return <span className="term term--bnode">_:{term.value}</span>;
  }

  const display = term.value.startsWith("http")
    ? `<${term.value.replace(/^https?:\/\//, "")}>`
    : term.value;

  return (
    <span className={`term term--${kind}`} title={term.value}>
      {display}
    </span>
  );
}
