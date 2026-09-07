import { useState, useEffect, useRef, useCallback } from "react";
import { searchProducts, keywordSearch, getAutocomplete, getFilters } from "./api";
import "./index.css";

/* ============================================================
   SEARCH BAR COMPONENT
   ============================================================ */
function SearchBar({ onSearch, onExampleClick }) {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const inputRef = useRef(null);
  const debounceRef = useRef(null);

  // Debounced autocomplete
  useEffect(() => {
    if (query.length < 2) {
      setSuggestions([]);
      return;
    }
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const data = await getAutocomplete(query);
        setSuggestions(data.suggestions || []);
        setShowSuggestions(true);
      } catch {
        setSuggestions([]);
      }
    }, 250);
    return () => clearTimeout(debounceRef.current);
  }, [query]);

  const handleSubmit = useCallback(
    (q) => {
      const searchQuery = q || query;
      if (!searchQuery.trim()) return;
      setShowSuggestions(false);
      setSuggestions([]);
      onSearch(searchQuery.trim());
    },
    [query, onSearch]
  );

  const handleKeyDown = (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIdx((prev) => Math.min(prev + 1, suggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIdx((prev) => Math.max(prev - 1, -1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (activeIdx >= 0 && suggestions[activeIdx]) {
        setQuery(suggestions[activeIdx]);
        handleSubmit(suggestions[activeIdx]);
      } else {
        handleSubmit();
      }
    } else if (e.key === "Escape") {
      setShowSuggestions(false);
    }
  };

  return (
    <div className="search-container">
      <div className="search-bar">
        <span className="search-icon">🔍</span>
        <input
          ref={inputRef}
          id="search-input"
          className="search-input"
          type="text"
          placeholder="Search products naturally... e.g. 'warm jacket for winter'"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setActiveIdx(-1);
          }}
          onKeyDown={handleKeyDown}
          onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
          onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
          autoComplete="off"
        />
        <button
          className={`search-clear ${query ? "visible" : ""}`}
          onClick={() => {
            setQuery("");
            setSuggestions([]);
            inputRef.current?.focus();
          }}
          aria-label="Clear search"
        >
          ✕
        </button>
      </div>
      {showSuggestions && suggestions.length > 0 && (
        <div className="autocomplete-dropdown">
          {suggestions.map((s, i) => (
            <div
              key={s}
              className={`autocomplete-item ${i === activeIdx ? "active" : ""}`}
              onMouseDown={() => {
                setQuery(s);
                handleSubmit(s);
              }}
            >
              <span className="ac-icon">↗</span>
              {s}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ============================================================
   FILTER SIDEBAR
   ============================================================ */
function FilterSidebar({ filters, activeFilters, onFilterChange, onClear }) {
  if (!filters) return null;

  return (
    <aside className="sidebar">
      {/* Categories */}
      {filters.categories?.length > 0 && (
        <div className="filter-section">
          <div className="filter-title">Category</div>
          <div
            className={`filter-option ${!activeFilters.category ? "selected" : ""}`}
            onClick={() => onFilterChange("category", null)}
          >
            <div className="filter-radio" />
            All Categories
          </div>
          {filters.categories.map((cat) => (
            <div
              key={cat.category_id}
              className={`filter-option ${activeFilters.category === cat.name ? "selected" : ""}`}
              onClick={() => onFilterChange("category", cat.name)}
            >
              <div className="filter-radio" />
              {cat.name}
            </div>
          ))}
        </div>
      )}

      {/* Brands */}
      {filters.brands?.length > 0 && (
        <div className="filter-section">
          <div className="filter-title">Brand</div>
          <div
            className={`filter-option ${!activeFilters.brand ? "selected" : ""}`}
            onClick={() => onFilterChange("brand", null)}
          >
            <div className="filter-radio" />
            All Brands
          </div>
          {filters.brands.slice(0, 10).map((brand) => (
            <div
              key={brand}
              className={`filter-option ${activeFilters.brand === brand ? "selected" : ""}`}
              onClick={() => onFilterChange("brand", brand)}
            >
              <div className="filter-radio" />
              {brand}
            </div>
          ))}
        </div>
      )}

      {/* Price Range */}
      <div className="filter-section">
        <div className="filter-title">Price Range</div>
        <div className="price-range-inputs">
          <input
            className="price-input"
            type="number"
            placeholder={`$${Math.floor(filters.price_range?.min || 0)}`}
            value={activeFilters.min_price || ""}
            onChange={(e) => onFilterChange("min_price", e.target.value || null)}
          />
          <span className="price-separator">—</span>
          <input
            className="price-input"
            type="number"
            placeholder={`$${Math.ceil(filters.price_range?.max || 1000)}`}
            value={activeFilters.max_price || ""}
            onChange={(e) => onFilterChange("max_price", e.target.value || null)}
          />
        </div>
      </div>

      {/* Clear Filters */}
      <button className="filter-clear-btn" onClick={onClear}>
        Clear All Filters
      </button>
    </aside>
  );
}

/* ============================================================
   PRODUCT CARD
   ============================================================ */
function ProductCard({ result }) {
  const { product, score } = result;
  const [imgError, setImgError] = useState(false);

  const renderStars = (rating) => {
    const stars = [];
    const full = Math.floor(rating);
    for (let i = 0; i < 5; i++) {
      stars.push(
        <span key={i} style={{ opacity: i < full ? 1 : 0.3 }}>
          ★
        </span>
      );
    }
    return stars;
  };

  return (
    <div className="product-card" id={`product-${product.product_id}`}>
      <div className="product-card-image">
        {product.image_url && !imgError ? (
          <img
            src={product.image_url}
            alt={product.name}
            loading="lazy"
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="product-card-image-placeholder">📦</div>
        )}
        {score !== undefined && score !== null && (
          <span className="product-score">{Math.round(score * 100)}% match</span>
        )}
      </div>
      <div className="product-card-body">
        {product.category_name && (
          <div className="product-category">{product.category_name}</div>
        )}
        <div className="product-name">{product.name}</div>
        <div className="product-description">{product.description}</div>
        <div className="product-meta">
          <span className="product-price">
            {product.price ? `$${Number(product.price).toFixed(2)}` : "N/A"}
          </span>
          <span className="product-rating">
            {renderStars(product.rating_avg)}
            <span className="product-rating-value">{product.rating_avg?.toFixed(1)}</span>
          </span>
        </div>
        {product.brand && <div className="product-brand">by {product.brand}</div>}
      </div>
    </div>
  );
}

/* ============================================================
   LOADING SKELETON
   ============================================================ */
function LoadingSkeleton({ count = 6 }) {
  return (
    <div className="results-grid">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="skeleton-card">
          <div className="skeleton skeleton-image" />
          <div className="skeleton-body">
            <div className="skeleton skeleton-line short" />
            <div className="skeleton skeleton-line medium" />
            <div className="skeleton skeleton-line" />
            <div className="skeleton skeleton-line short" />
          </div>
        </div>
      ))}
    </div>
  );
}

/* ============================================================
   HERO / LANDING
   ============================================================ */
function Hero({ onSearch }) {
  const examples = [
    "warm winter jacket for men",
    "comfortable shoes for flat feet",
    "noise cancelling headphones",
    "gift for a programmer",
    "kitchen essentials for beginners",
    "workout equipment for home",
  ];

  return (
    <div className="hero-container fade-in-up">
      <span className="hero-badge">✨ Powered by AI embeddings</span>
      <h1 className="hero-title">
        Search by <span className="accent">meaning</span>,<br />
        not just keywords
      </h1>
      <p className="hero-subtitle">
        Describe what you're looking for in natural language. Our semantic engine
        understands intent and finds products that match your meaning, not just your words.
      </p>
      <div className="hero-search">
        <SearchBar onSearch={onSearch} />
      </div>
      <div className="hero-examples">
        {examples.map((ex) => (
          <button
            key={ex}
            className="hero-example-chip"
            onClick={() => onSearch(ex)}
          >
            {ex}
          </button>
        ))}
      </div>
    </div>
  );
}

/* ============================================================
   MAIN APP
   ============================================================ */
export default function App() {
  const [searchQuery, setSearchQuery] = useState("");
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchType, setSearchType] = useState("semantic");
  const [filters, setFilters] = useState(null);
  const [activeFilters, setActiveFilters] = useState({});
  const [hasSearched, setHasSearched] = useState(false);

  // Load filter options on mount
  useEffect(() => {
    getFilters()
      .then(setFilters)
      .catch((e) => console.warn("Failed to load filters:", e));
  }, []);

  // Execute search
  const doSearch = useCallback(
    async (query, type = searchType, currentFilters = activeFilters) => {
      if (!query?.trim()) return;
      setSearchQuery(query);
      setHasSearched(true);
      setLoading(true);
      setError(null);

      try {
        const searchFn = type === "keyword" ? keywordSearch : searchProducts;
        const data = await searchFn(query, { ...currentFilters, limit: 40 });
        setResults(data);
      } catch (err) {
        console.error("Search error:", err);
        setError(err.message || "Search failed. Is the backend running?");
        setResults(null);
      } finally {
        setLoading(false);
      }
    },
    [searchType, activeFilters]
  );

  // Re-search when filters change
  const handleFilterChange = (key, value) => {
    const newFilters = { ...activeFilters, [key]: value };
    if (value === null || value === "") {
      delete newFilters[key];
    }
    setActiveFilters(newFilters);
    if (searchQuery) {
      doSearch(searchQuery, searchType, newFilters);
    }
  };

  const clearFilters = () => {
    setActiveFilters({});
    if (searchQuery) {
      doSearch(searchQuery, searchType, {});
    }
  };

  const handleSearchTypeChange = (type) => {
    setSearchType(type);
    if (searchQuery) {
      doSearch(searchQuery, type, activeFilters);
    }
  };

  // If no search yet, show the hero/landing page
  if (!hasSearched) {
    return (
      <div className="app">
        <Hero onSearch={(q) => doSearch(q)} />
      </div>
    );
  }

  return (
    <div className="app">
      {/* Header */}
      <header className="app-header">
        <div
          className="app-logo"
          style={{ cursor: "pointer" }}
          onClick={() => {
            setHasSearched(false);
            setResults(null);
            setSearchQuery("");
            setActiveFilters({});
          }}
        >
          <div className="app-logo-icon">🧠</div>
          <span className="app-logo-text">SemanticSearch</span>
          <span className="app-logo-badge">AI</span>
        </div>

        <SearchBar onSearch={(q) => doSearch(q)} />

        <div className="search-mode-toggle">
          <button
            className={`mode-btn ${searchType === "semantic" ? "active" : ""}`}
            onClick={() => handleSearchTypeChange("semantic")}
          >
            🧠 Semantic
          </button>
          <button
            className={`mode-btn ${searchType === "keyword" ? "active" : ""}`}
            onClick={() => handleSearchTypeChange("keyword")}
          >
            🔤 Keyword
          </button>
        </div>
      </header>

      {/* Main content */}
      <main className="app-main">
        <FilterSidebar
          filters={filters}
          activeFilters={activeFilters}
          onFilterChange={handleFilterChange}
          onClear={clearFilters}
        />

        <div className="results-area">
          {/* Results header */}
          {results && !loading && (
            <div className="results-header fade-in">
              <span className="results-count">
                <strong>{results.total}</strong> results for "{results.query}"
              </span>
              <span
                className={`search-type-badge ${results.search_type}`}
              >
                {results.search_type} search
              </span>
            </div>
          )}

          {/* Error state */}
          {error && (
            <div className="state-container fade-in">
              <div className="state-icon">⚠️</div>
              <div className="state-title">Search Error</div>
              <div className="state-subtitle">{error}</div>
            </div>
          )}

          {/* Loading state */}
          {loading && <LoadingSkeleton />}

          {/* Results */}
          {!loading && results && results.results?.length > 0 && (
            <div className="results-grid">
              {results.results.map((r) => (
                <ProductCard key={r.product.product_id} result={r} />
              ))}
            </div>
          )}

          {/* No results */}
          {!loading && results && results.results?.length === 0 && (
            <div className="state-container fade-in-up">
              <div className="state-icon">🔎</div>
              <div className="state-title">No products found</div>
              <div className="state-subtitle">
                Try a different search query or adjust your filters.
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
