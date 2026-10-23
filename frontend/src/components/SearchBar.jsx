import { useState, useEffect, useRef, useCallback } from "react";
import { getAutocomplete } from "../api";
import Icon from "./Icon";

/**
 * The query box. Framed as binding a value to the ?query variable, because the
 * SPARQL panel a few pixels away is built from exactly this string.
 */
export default function SearchBar({ onSearch, initial = "", size = "md" }) {
  const [query, setQuery] = useState(initial);
  const [suggestions, setSuggestions] = useState([]);
  const [open, setOpen] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const inputRef = useRef(null);
  const debounceRef = useRef(null);

  useEffect(() => setQuery(initial), [initial]);

  // Debounced prefix lookup — one request per pause, not per keystroke.
  useEffect(() => {
    if (query.trim().length < 2) {
      setSuggestions([]);
      return;
    }
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const data = await getAutocomplete(query);
        setSuggestions(data.suggestions || []);
        setOpen(true);
      } catch {
        setSuggestions([]);
      }
    }, 250);
    return () => clearTimeout(debounceRef.current);
  }, [query]);

  const submit = useCallback(
    (q) => {
      const value = (q ?? query).trim();
      if (!value) return;
      setOpen(false);
      setSuggestions([]);
      onSearch(value);
    },
    [query, onSearch]
  );

  const onKeyDown = (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIdx((i) => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIdx((i) => Math.max(i - 1, -1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const picked = activeIdx >= 0 ? suggestions[activeIdx] : null;
      if (picked) setQuery(picked);
      submit(picked);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div className={`qbox qbox--${size}`}>
      <div className="qbox__field">
        <Icon name="search" size={size === "lg" ? 20 : 16} className="qbox__icon" />
        <span className="qbox__var" aria-hidden="true">
          ?query
        </span>
        <input
          ref={inputRef}
          className="qbox__input"
          type="text"
          value={query}
          placeholder="Describe what you mean — “something to keep coffee hot”"
          aria-label="Search the catalogue graph"
          autoComplete="off"
          onChange={(e) => {
            setQuery(e.target.value);
            setActiveIdx(-1);
          }}
          onKeyDown={onKeyDown}
          onFocus={() => suggestions.length > 0 && setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 160)}
        />
        {query && (
          <button
            className="qbox__clear"
            aria-label="Clear the query"
            onClick={() => {
              setQuery("");
              setSuggestions([]);
              inputRef.current?.focus();
            }}
          >
            <Icon name="close" size={14} />
          </button>
        )}
        <button className="qbox__go" onClick={() => submit()}>
          <span>Search</span>
          <Icon name="arrowRight" size={15} />
        </button>
      </div>

      {open && suggestions.length > 0 && (
        <ul className="qbox__menu" role="listbox">
          {suggestions.map((s, i) => (
            <li key={s}>
              <button
                type="button"
                role="option"
                aria-selected={i === activeIdx}
                className={`qbox__option ${i === activeIdx ? "is-active" : ""}`}
                onMouseDown={() => {
                  setQuery(s);
                  submit(s);
                }}
              >
                <span className="qbox__option-label">{s}</span>
                <span className="term term--prop">schema:name</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
