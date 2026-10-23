// Override at build/dev time with VITE_API_BASE (see .env.example).
const API_BASE = import.meta.env?.VITE_API_BASE || "http://localhost:8000/api";

/**
 * Perform a semantic search.
 * @param {string} query - Search query string
 * @param {Object} filters - Optional filter parameters
 * @returns {Promise<Object>} Search response with results
 */
export async function searchProducts(query, filters = {}) {
  const params = new URLSearchParams({ q: query });

  if (filters.category) params.set("category", filters.category);
  if (filters.brand) params.set("brand", filters.brand);
  if (filters.min_price !== undefined && filters.min_price !== null && filters.min_price !== "")
    params.set("min_price", filters.min_price);
  if (filters.max_price !== undefined && filters.max_price !== null && filters.max_price !== "")
    params.set("max_price", filters.max_price);
  if (filters.min_rating !== undefined && filters.min_rating !== null)
    params.set("min_rating", filters.min_rating);
  if (filters.limit) params.set("limit", filters.limit);
  if (filters.offset) params.set("offset", filters.offset);

  const res = await fetch(`${API_BASE}/search?${params}`);
  if (!res.ok) throw new Error(`Search failed: ${res.status}`);
  return res.json();
}

/**
 * Perform a keyword-based search.
 */
export async function keywordSearch(query, filters = {}) {
  const params = new URLSearchParams({ q: query });

  if (filters.category) params.set("category", filters.category);
  if (filters.brand) params.set("brand", filters.brand);
  if (filters.min_price !== undefined && filters.min_price !== null && filters.min_price !== "")
    params.set("min_price", filters.min_price);
  if (filters.max_price !== undefined && filters.max_price !== null && filters.max_price !== "")
    params.set("max_price", filters.max_price);
  if (filters.limit) params.set("limit", filters.limit);
  if (filters.offset) params.set("offset", filters.offset);

  const res = await fetch(`${API_BASE}/search/keyword?${params}`);
  if (!res.ok) throw new Error(`Keyword search failed: ${res.status}`);
  return res.json();
}

/**
 * Get autocomplete suggestions.
 */
export async function getAutocomplete(query) {
  const params = new URLSearchParams({ q: query, limit: 8 });
  const res = await fetch(`${API_BASE}/autocomplete?${params}`);
  if (!res.ok) throw new Error(`Autocomplete failed: ${res.status}`);
  return res.json();
}

/**
 * Get available filter options (categories, brands, price range).
 */
export async function getFilters() {
  const res = await fetch(`${API_BASE}/filters`);
  if (!res.ok) throw new Error(`Filters failed: ${res.status}`);
  return res.json();
}

/**
 * Products nearest to one product, by its stored embedding.
 */
export async function getSimilar(productId, limit = 12) {
  const res = await fetch(`${API_BASE}/product/${productId}/similar?limit=${limit}`);
  if (!res.ok) throw new Error(`Similar products failed: ${res.status}`);
  return res.json();
}

/**
 * Record that a result was opened. Fire-and-forget: feedback must never
 * interrupt or slow the interface, so failures are swallowed.
 */
export function recordClick(query, productId) {
  return fetch(`${API_BASE}/click`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, product_id: productId }),
    keepalive: true,
  }).catch(() => {});
}
