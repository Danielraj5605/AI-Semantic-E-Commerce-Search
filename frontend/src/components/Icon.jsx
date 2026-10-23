/**
 * Line icons drawn on a 24px grid with a 1.6 stroke, so they sit with the type
 * instead of competing with it. One component, so every glyph in the interface
 * comes from the same hand.
 */

const PATHS = {
  search: <><circle cx="11" cy="11" r="6.5" /><path d="m20 20-4.2-4.2" /></>,
  close: <path d="M6 6l12 12M18 6 6 18" />,
  chevron: <path d="m9 6 6 6-6 6" />,
  chevronDown: <path d="m6 9 6 6 6-6" />,
  arrowRight: <path d="M5 12h14M13 6l6 6-6 6" />,
  arrowUpRight: <path d="M7 17 17 7M8 7h9v9" />,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4" /></>,
  moon: <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" />,
  graph: <><circle cx="6" cy="6" r="2.2" /><circle cx="18" cy="8" r="2.2" /><circle cx="9" cy="18" r="2.2" /><path d="m8 7 7.9 .7M7 8l1.6 7.9M16.5 9.7l-5.8 6.7" /></>,
  layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="m3 13 9 5 9-5" /></>,
  code: <path d="m8 7-5 5 5 5M16 7l5 5-5 5" />,
  check: <path d="m5 12.5 4.5 4.5L19 7.5" />,
  alert: <><path d="M12 3.5 21.5 20h-19L12 3.5Z" /><path d="M12 10v4.5M12 17.5v.01" /></>,
  shield: <><path d="M12 3 4.5 6v6c0 4.5 3.2 7.8 7.5 9 4.3-1.2 7.5-4.5 7.5-9V6L12 3Z" /><path d="m8.8 12 2.2 2.2 4.2-4.4" /></>,
  copy: <><rect x="8.5" y="8.5" width="11" height="11" rx="2" /><path d="M15.5 8.5V6a1.5 1.5 0 0 0-1.5-1.5H6A1.5 1.5 0 0 0 4.5 6v8A1.5 1.5 0 0 0 6 15.5h2.5" /></>,
  image: <><rect x="3.5" y="4.5" width="17" height="15" rx="2" /><circle cx="9" cy="10" r="1.6" /><path d="m20.5 16-5-5-8 8.5" /></>,
  star: <path d="m12 3.6 2.6 5.3 5.8.8-4.2 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.2-4.1 5.8-.8L12 3.6Z" />,
  spark: <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6" />,
  filter: <path d="M4 6h16M7 12h10M10 18h4" />,
};

export default function Icon({ name, size = 16, className = "", fill = false, title }) {
  return (
    <svg
      className={`icon ${className}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={fill ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden={title ? undefined : "true"}
      role={title ? "img" : undefined}
    >
      {title && <title>{title}</title>}
      {PATHS[name]}
    </svg>
  );
}

/** The mark: a subject, a predicate edge and an object; one triple. */
export function Logo({ size = 22 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" className="logo">
      <path d="M8 22 16 9l8 13" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M8 22h16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" opacity=".45" />
      <circle cx="16" cy="9" r="3.6" className="logo__accent" />
      <circle cx="8" cy="22" r="3" fill="currentColor" />
      <circle cx="24" cy="22" r="3" fill="currentColor" />
    </svg>
  );
}
