"""Search service — semantic and keyword search logic."""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, text, and_, cast, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Product, ProductEmbedding, Category
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
) -> tuple[list[dict], int]:
    """Perform semantic similarity search using pgvector cosine distance.

    Returns:
        A tuple of (results_list, total_count) where each result is a dict
        with product fields and a similarity score.
    """
    # 1. Encode the query
    query_embedding = encode_text(query)

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
    filters = []
    if category:
        filters.append(func.lower(Category.name) == category.lower())
    if brand:
        filters.append(func.lower(Product.brand) == brand.lower())
    if min_price is not None:
        filters.append(Product.price >= min_price)
    if max_price is not None:
        filters.append(Product.price <= max_price)
    if min_rating is not None:
        filters.append(Product.rating_avg >= min_rating)

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
    results = []
    for product, score, category_name in rows:
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
            "score": round(float(score), 4) if score else 0.0,
        })

    return results, total


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
    search_pattern = f"%{query}%"

    stmt = (
        select(Product, Category.name.label("category_name"))
        .outerjoin(Category, Product.category_id == Category.category_id)
        .where(
            (Product.name.ilike(search_pattern))
            | (Product.description.ilike(search_pattern))
            | (Product.brand.ilike(search_pattern))
        )
    )

    # Apply filters
    filters = []
    if category:
        filters.append(func.lower(Category.name) == category.lower())
    if brand:
        filters.append(func.lower(Product.brand) == brand.lower())
    if min_price is not None:
        filters.append(Product.price >= min_price)
    if max_price is not None:
        filters.append(Product.price <= max_price)
    if min_rating is not None:
        filters.append(Product.rating_avg >= min_rating)

    if filters:
        stmt = stmt.where(and_(*filters))

    # Count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Paginate
    stmt = stmt.order_by(Product.rating_avg.desc()).offset(offset).limit(limit)

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


async def get_autocomplete_suggestions(
    db: AsyncSession,
    prefix: str,
    limit: int = 8,
) -> list[str]:
    """Return product name suggestions matching a prefix."""
    stmt = (
        select(Product.name)
        .where(Product.name.ilike(f"{prefix}%"))
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
