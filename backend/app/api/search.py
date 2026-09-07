"""Search API routes."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from cachetools import TTLCache

from app.db.session import get_db
from app.models.schemas import SearchResponse, AutocompleteResponse, FilterOptions
from app.services.search_service import (
    semantic_search,
    keyword_search,
    get_autocomplete_suggestions,
    get_filter_options,
)
from app.models.models import SearchLog
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


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    category: Optional[str] = Query(None),
    brand: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    min_rating: Optional[float] = Query(None, ge=0, le=5),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Semantic search endpoint — encodes query and finds similar products."""
    cache_key = _cache_key(
        q, category=category, brand=brand,
        min_price=min_price, max_price=max_price,
        min_rating=min_rating, limit=limit, offset=offset,
    )

    # Check cache
    if cache_key in _search_cache:
        logger.debug("Cache hit for: %s", q)
        return _search_cache[cache_key]

    try:
        results, total = await semantic_search(
            db, q,
            limit=limit, offset=offset,
            category=category, brand=brand,
            min_price=min_price, max_price=max_price,
            min_rating=min_rating,
        )
        search_type = "semantic"
    except Exception as e:
        # Fallback to keyword search if embedding service fails
        logger.warning("Semantic search failed, falling back to keyword: %s", e)
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

    # Cache the response
    _search_cache[cache_key] = response

    # Log the search (fire-and-forget, don't block the response)
    try:
        log_entry = SearchLog(query_text=q)
        db.add(log_entry)
    except Exception as log_err:
        logger.warning("Failed to log search: %s", log_err)

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
