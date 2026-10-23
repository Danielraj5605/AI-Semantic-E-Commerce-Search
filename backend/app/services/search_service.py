"""Search service — semantic and keyword search logic."""

import logging
import math
import re
from typing import Optional
from uuid import UUID

import numpy as np
from sqlalchemy import select, func, text, and_, cast, String, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Product, ProductEmbedding, Category, SearchLog
from app.services.embedding_service import encode_text
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def semantic_search(
    db: AsyncSession,
    query: str,
    limit: int = 20,
    offset: int = 0,
    category: Optional[str] = None,
    brand: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_rating: Optional[float] = None,
    min_similarity: Optional[float] = None,
    query_embedding: Optional[list[float]] = None,
    exclude_id: Optional[UUID] = None,
) -> tuple[list[dict], int]:
    """Perform semantic similarity search using pgvector cosine distance.

    `query_embedding` skips the encoder (used by "find similar", which ranks by a
    stored vector and so works even when the model is down); `exclude_id` keeps
    the seed product out of its own neighbours.

    A nearest-neighbour scan has no natural stopping point: every embedded
    product has *some* distance to the query, so without a relevance floor the
    whole catalogue comes back ranked, and whatever happens to be second-least
    unrelated appears directly beneath the real answer. `min_similarity` is that
    floor; pass 0 to disable it and get the raw ranking.

    Returns:
        A tuple of (results_list, total_count) where each result is a dict
        with product fields and a similarity score.
    """
    if min_similarity is None:
        min_similarity = settings.min_similarity
    # 1. Encode the query
    if query_embedding is None:
        query_embedding = encode_text(query)
    category_names = await expand_category(db, category)

    if settings.is_sqlite:
        return await _semantic_search_in_python(
            db, query_embedding, limit, offset,
            category, brand, min_price, max_price, min_rating, min_similarity,
            category_names, exclude_id,
        )

    # 2. Build the base query with cosine distance
    # pgvector's <=> operator returns cosine distance (0 = identical, 2 = opposite)
    # We convert to a similarity score: 1 - distance
    cosine_distance = ProductEmbedding.embedding.cosine_distance(query_embedding)
    similarity_score = (1 - cosine_distance).label("score")

    stmt = (
        select(
            Product,
            similarity_score,
            Category.name.label("category_name"),
        )
        .join(ProductEmbedding, Product.product_id == ProductEmbedding.product_id)
        .outerjoin(Category, Product.category_id == Category.category_id)
    )

    # 3. Apply filters
    filters = _structural_filters(category_names, brand, min_price, max_price, min_rating, exclude_id)

    # The relevance floor exists to stop an open-ended query from dragging the
    # whole catalogue back with it. An explicit category or brand already does
    # that job, and does it better — so when the caller has named one, the floor
    # stands down and every member of the selected class is returned, ranked.
    #
    # The distinction is the one the UI makes everywhere else: class membership
    # is *asserted*, the similarity score is only *believed*. Dropping an
    # asserted member because a belief score is low would invert that.
    structurally_constrained = bool(category or brand)

    # It lands in WHERE rather than being trimmed afterwards — otherwise `total`
    # would count rows the user is never shown, and pagination would stride
    # over the gaps.
    if min_similarity and min_similarity > 0 and not structurally_constrained:
        filters.append(cosine_distance <= (1 - min_similarity))

    if filters:
        stmt = stmt.where(and_(*filters))

    # 4. Count total results (for pagination info)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # 5. Order by similarity and paginate
    stmt = stmt.order_by(cosine_distance.asc()).offset(offset).limit(limit)

    result = await db.execute(stmt)
    rows = result.all()

    # 6. Format results
    results = [
        _format_result(product, category_name, score)
        for product, score, category_name in rows
    ]

    return results, total


async def expand_category(db: AsyncSession, category: Optional[str]) -> Optional[list[str]]:
    """Lower-cased names of a category and all its descendants.

    This is rdfs:subClassOf entailment: asking for Electronics must also return
    Laptops, because every Laptop *is* an Electronics. A leaf (or unknown) name
    expands to just itself, so flat categories behave exactly as before.
    """
    if not category:
        return None
    rows = (await db.execute(select(Category.category_id, Category.name, Category.parent_category_id))).all()
    children: dict[int, list] = {}
    for cid, _name, pid in rows:
        if pid is not None:
            children.setdefault(pid, []).append(cid)
    names = {cid: name for cid, name, _ in rows}

    start = [cid for cid, name in names.items() if name.lower() == category.lower()]
    seen: set[int] = set()
    stack = list(start)
    while stack:  # iterative, and `seen` makes a parent cycle harmless
        cid = stack.pop()
        if cid in seen:
            continue
        seen.add(cid)
        stack.extend(children.get(cid, []))
    return sorted({names[c].lower() for c in seen} | {category.lower()})


def _structural_filters(category_names, brand, min_price, max_price, min_rating, exclude_id=None) -> list:
    filters = []
    if exclude_id is not None:
        filters.append(Product.product_id != exclude_id)
    if category_names:
        filters.append(func.lower(Category.name).in_(category_names))
    if brand:
        filters.append(func.lower(Product.brand) == brand.lower())
    if min_price is not None:
        filters.append(Product.price >= min_price)
    if max_price is not None:
        filters.append(Product.price <= max_price)
    if min_rating is not None:
        filters.append(Product.rating_avg >= min_rating)
    return filters


def _format_result(product: Product, category_name: Optional[str], score) -> dict:
    return {
        "product": {
            "product_id": product.product_id,
            "name": product.name,
            "description": product.description,
            "category_id": product.category_id,
            "category_name": category_name,
            "brand": product.brand,
            "price": float(product.price) if product.price else None,
            "stock_quantity": product.stock_quantity,
            "rating_avg": product.rating_avg or 0.0,
            "image_url": product.image_url,
            "created_at": product.created_at,
        },
        "score": round(float(score), 4) if score else 0.0,
    }


async def _semantic_search_in_python(
    db: AsyncSession,
    query_embedding: list[float],
    limit: int,
    offset: int,
    category: Optional[str],
    brand: Optional[str],
    min_price: Optional[float],
    max_price: Optional[float],
    min_rating: Optional[float],
    min_similarity: float,
    category_names: Optional[list[str]] = None,
    exclude_id: Optional[UUID] = None,
) -> tuple[list[dict], int]:
    """Same contract as the pgvector path, for the local SQLite database.

    Structural filters still run in SQL; only the ranking moves to Python.
    Embeddings are stored normalised, so cosine similarity is a dot product.
    """
    stmt = (
        select(Product, ProductEmbedding.embedding, Category.name.label("category_name"))
        .join(ProductEmbedding, Product.product_id == ProductEmbedding.product_id)
        .outerjoin(Category, Product.category_id == Category.category_id)
    )
    filters = _structural_filters(category_names, brand, min_price, max_price, min_rating, exclude_id)
    if filters:
        stmt = stmt.where(and_(*filters))

    rows = (await db.execute(stmt)).all()
    q = np.asarray(query_embedding, dtype=np.float32)
    scored = [
        (product, float(np.dot(q, np.asarray(emb, dtype=np.float32))), category_name)
        for product, emb, category_name in rows
    ]

    # Mirrors the SQL path: an explicit category/brand disables the floor.
    if min_similarity and min_similarity > 0 and not (category or brand):
        scored = [row for row in scored if row[1] >= min_similarity]

    scored.sort(key=lambda row: row[1], reverse=True)
    page = scored[offset:offset + limit]
    return [_format_result(p, c, s) for p, s, c in page], len(scored)


_STOPWORDS = {
    "a", "an", "the", "for", "to", "of", "and", "or", "with", "in", "on", "that",
    "is", "are", "my", "me", "i", "something", "some",
}


def _keyword_terms(query: str) -> list[str]:
    """Significant lower-cased words of a query; the raw phrase if none survive."""
    words = re.findall(r"[\w'&-]+", query.lower())
    terms = [w for w in words if w not in _STOPWORDS and len(w) > 1]
    return terms or [query.strip().lower()]


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def keyword_search(
    db: AsyncSession,
    query: str,
    limit: int = 20,
    offset: int = 0,
    category: Optional[str] = None,
    brand: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_rating: Optional[float] = None,
) -> tuple[list[dict], int]:
    """Fallback keyword search using PostgreSQL ILIKE matching.

    This is simpler and faster but only matches literal substrings.
    Used as a fallback if the embedding service is unavailable.
    """
    terms = _keyword_terms(query)
    stmt = select(Product, Category.name.label("category_name")).outerjoin(
        Category, Product.category_id == Category.category_id
    )
    # Every term must appear somewhere (AND), so "warm jacket" matches a product
    # that says "jacket" in its name and "warm" in its description. Matching the
    # whole phrase as one substring made multi-word queries almost never hit.
    name_hits = []
    for term in terms:
        pattern = f"%{_escape_like(term)}%"
        in_name = Product.name.ilike(pattern, escape="\\")
        stmt = stmt.where(
            in_name
            | Product.description.ilike(pattern, escape="\\")
            | Product.brand.ilike(pattern, escape="\\")
        )
        name_hits.append(case((in_name, 1), else_=0))

    # Apply filters
    filters = _structural_filters(
        await expand_category(db, category), brand, min_price, max_price, min_rating
    )

    if filters:
        stmt = stmt.where(and_(*filters))

    # Count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Paginate
    # Terms found in the name rank first; rating breaks ties.
    stmt = stmt.order_by(sum(name_hits).desc(), Product.rating_avg.desc()).offset(offset).limit(limit)

    result = await db.execute(stmt)
    rows = result.all()

    results = []
    for product, category_name in rows:
        results.append({
            "product": {
                "product_id": product.product_id,
                "name": product.name,
                "description": product.description,
                "category_id": product.category_id,
                "category_name": category_name,
                "brand": product.brand,
                "price": float(product.price) if product.price else None,
                "stock_quantity": product.stock_quantity,
                "rating_avg": product.rating_avg or 0.0,
                "image_url": product.image_url,
                "created_at": product.created_at,
            },
            "score": 1.0,  # No real relevance score for keyword search
        })

    return results, total


async def apply_click_boost(db: AsyncSession, results: list[dict], weight: float) -> list[dict]:
    """Re-order a page of semantic results by click popularity; scores are untouched."""
    if weight <= 0 or len(results) < 2:
        return results
    ids = [r["product"]["product_id"] for r in results]
    rows = (
        await db.execute(
            select(SearchLog.clicked_product_id, func.count())
            .where(SearchLog.clicked_product_id.in_(ids))
            .group_by(SearchLog.clicked_product_id)
        )
    ).all()
    clicks = {pid: n for pid, n in rows}
    if not clicks:
        return results
    return sorted(
        results,
        key=lambda r: r["score"] * (1 + weight * math.log1p(clicks.get(r["product"]["product_id"], 0))),
        reverse=True,
    )


async def get_product_row(db: AsyncSession, product_id: UUID) -> Optional[dict]:
    """One product in the same shape as a search result's `product`, or None."""
    row = (
        await db.execute(
            select(Product, Category.name.label("category_name"))
            .outerjoin(Category, Product.category_id == Category.category_id)
            .where(Product.product_id == product_id)
        )
    ).first()
    if row is None:
        return None
    return _format_result(row[0], row[1], 0)["product"]


async def similar_products(
    db: AsyncSession, product_id: UUID, limit: int = 10, offset: int = 0,
    min_similarity: Optional[float] = None,
) -> Optional[tuple[dict, list[dict], int]]:
    """Neighbours of a product by its stored embedding.

    Returns (seed_product, results, total), or None if the product is unknown or
    has no embedding yet.
    """
    seed = await get_product_row(db, product_id)
    vector = await db.scalar(
        select(ProductEmbedding.embedding).where(ProductEmbedding.product_id == product_id)
    )
    if seed is None or vector is None:
        return None
    results, total = await semantic_search(
        db, seed["name"], limit=limit, offset=offset,
        min_similarity=min_similarity,
        query_embedding=[float(x) for x in vector],
        exclude_id=product_id,
    )
    return seed, results, total


async def get_autocomplete_suggestions(
    db: AsyncSession,
    prefix: str,
    limit: int = 8,
) -> list[str]:
    """Return product name suggestions matching a prefix."""
    stmt = (
        select(Product.name)
        .where(Product.name.ilike(f"{_escape_like(prefix)}%", escape="\\"))
        .distinct()
        .order_by(Product.name)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]


async def get_filter_options(db: AsyncSession) -> dict:
    """Return available filter values for the frontend sidebar."""
    # Categories
    cat_stmt = select(Category).order_by(Category.name)
    cat_result = await db.execute(cat_stmt)
    categories = cat_result.scalars().all()

    # Brands
    brand_stmt = (
        select(Product.brand)
        .where(Product.brand.isnot(None))
        .distinct()
        .order_by(Product.brand)
    )
    brand_result = await db.execute(brand_stmt)
    brands = [row[0] for row in brand_result.all()]

    # Price range
    price_stmt = select(
        func.min(Product.price).label("min_price"),
        func.max(Product.price).label("max_price"),
    )
    price_result = await db.execute(price_stmt)
    price_row = price_result.one()

    return {
        "categories": [
            {"category_id": c.category_id, "name": c.name, "parent_category_id": c.parent_category_id}
            for c in categories
        ],
        "brands": brands,
        "price_range": {
            "min": float(price_row.min_price) if price_row.min_price else 0,
            "max": float(price_row.max_price) if price_row.max_price else 0,
        },
    }
