"""Search API routes."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from cachetools import TTLCache

from app.db.session import get_db
from app.models.schemas import SearchResponse, AutocompleteResponse, FilterOptions, ClickEvent
from app.services.search_service import (
    semantic_search,
    keyword_search,
    get_autocomplete_suggestions,
    get_filter_options,
    apply_click_boost,
)
from app.models.models import SearchLog, Product
from app.services.embedding_service import EmbeddingUnavailable
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api", tags=["search"])

# In-memory cache for search results
_search_cache: TTLCache = TTLCache(
    maxsize=settings.cache_max_size,
    ttl=settings.cache_ttl_seconds,
)


def _cache_key(query: str, **kwargs) -> str:
    """Build a deterministic cache key from search parameters."""
    parts = [query.lower().strip()]
    for k in sorted(kwargs):
        if kwargs[k] is not None:
            parts.append(f"{k}={kwargs[k]}")
    return "|".join(parts)


async def _log_search(db: AsyncSession, query: str, product_id=None) -> None:
    """Record a search (or a click). Logging must never fail the request."""
    try:
        db.add(SearchLog(query_text=query, clicked_product_id=product_id))
        await db.commit()
    except Exception as err:
        await db.rollback()
        logger.warning("Failed to log search: %s", err)


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    category: Optional[str] = Query(None),
    brand: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    min_rating: Optional[float] = Query(None, ge=0, le=5),
    min_similarity: Optional[float] = Query(
        None, ge=0, le=1,
        description="Relevance floor; below this a product is not a result at all. "
                    "Defaults to settings.min_similarity; pass 0 for the raw ranking.",
    ),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Semantic search endpoint — encodes query and finds similar products."""
    cache_key = _cache_key(
        q, category=category, brand=brand,
        min_price=min_price, max_price=max_price,
        min_rating=min_rating, min_similarity=min_similarity,
        limit=limit, offset=offset,
    )

    # Check cache — a hit is still a search, so it is still logged
    if cache_key in _search_cache:
        logger.debug("Cache hit for: %s", q)
        await _log_search(db, q)
        return _search_cache[cache_key]

    try:
        results, total = await semantic_search(
            db, q,
            limit=limit, offset=offset,
            category=category, brand=brand,
            min_price=min_price, max_price=max_price,
            min_rating=min_rating, min_similarity=min_similarity,
        )
        results = await apply_click_boost(
            db, results, settings.click_boost_weight, settings.click_boost_min_clicks
        )
        search_type = "semantic"
    except EmbeddingUnavailable as e:
        # Only a missing encoder degrades to keyword. Database errors are not
        # caught here: keyword search would hit the same database and fail too,
        # so they surface as a 503 instead of a misleading "keyword" result.
        logger.warning("Embeddings unavailable, falling back to keyword: %s", e)
        results, total = await keyword_search(
            db, q,
            limit=limit, offset=offset,
            category=category, brand=brand,
            min_price=min_price, max_price=max_price,
            min_rating=min_rating,
        )
        search_type = "keyword"

    response = SearchResponse(
        query=q,
        total=total,
        results=results,
        search_type=search_type,
    )

    # Cache only real semantic answers; a degraded one must not outlive the outage
    if search_type == "semantic":
        _search_cache[cache_key] = response

    await _log_search(db, q)
    return response


@router.get("/search/keyword", response_model=SearchResponse)
async def search_keyword(
    q: str = Query(..., min_length=1, max_length=500),
    category: Optional[str] = Query(None),
    brand: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    min_rating: Optional[float] = Query(None, ge=0, le=5),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Keyword-based search endpoint (fallback / comparison baseline)."""
    results, total = await keyword_search(
        db, q,
        limit=limit, offset=offset,
        category=category, brand=brand,
        min_price=min_price, max_price=max_price,
        min_rating=min_rating,
    )
    return SearchResponse(
        query=q,
        total=total,
        results=results,
        search_type="keyword",
    )


@router.get("/autocomplete", response_model=AutocompleteResponse)
async def autocomplete(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(8, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """Return product name suggestions matching a prefix."""
    suggestions = await get_autocomplete_suggestions(db, q, limit)
    return AutocompleteResponse(suggestions=suggestions)


@router.get("/filters", response_model=FilterOptions)
async def filters(db: AsyncSession = Depends(get_db)):
    """Return available filter values for the sidebar."""
    options = await get_filter_options(db)
    return FilterOptions(**options)


@router.post("/click")
async def record_click(event: ClickEvent, db: AsyncSession = Depends(get_db)):
    """Record that the user opened a result — the signal personalisation would need."""
    exists = await db.scalar(select(Product.product_id).where(Product.product_id == event.product_id))
    if exists is None:
        raise HTTPException(status_code=404, detail="unknown product")
    await _log_search(db, event.query, product_id=event.product_id)
    return {"ok": True}
