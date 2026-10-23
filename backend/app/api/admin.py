"""Admin write endpoints (FR5): add, update and delete products.

Mounted only when ADMIN_TOKEN is set (see main.py); otherwise these routes do
not exist. Every write re-embeds the product so search never serves a stale
vector, and clears the result cache.
"""

import logging
import secrets
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import search as search_api
from app.config import get_settings
from app.db.session import get_db
from app.models.models import Category, Product, ProductEmbedding
from app.services.embedding_service import EmbeddingUnavailable, build_product_text, encode_text

logger = logging.getLogger(__name__)
settings = get_settings()


def require_admin(x_admin_token: Optional[str] = Header(None)) -> None:
    expected = settings.admin_token
    if not expected or not x_admin_token or not secrets.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=401, detail="invalid admin token")


router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class ProductWrite(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    category: Optional[str] = Field(None, description="Existing category name")
    brand: Optional[str] = Field(None, max_length=255)
    price: Optional[float] = Field(None, ge=0)
    stock_quantity: int = Field(0, ge=0)
    rating_avg: float = Field(0.0, ge=0, le=5)
    image_url: Optional[str] = None


class ProductPatch(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = Field(None, max_length=255)
    price: Optional[float] = Field(None, ge=0)
    stock_quantity: Optional[int] = Field(None, ge=0)
    rating_avg: Optional[float] = Field(None, ge=0, le=5)
    image_url: Optional[str] = None


async def _category_id(db: AsyncSession, name: str) -> int:
    cid = await db.scalar(select(Category.category_id).where(func.lower(Category.name) == name.lower()))
    if cid is None:
        raise HTTPException(status_code=422, detail=f"unknown category: {name}")
    return cid


async def _reembed(db: AsyncSession, product: Product) -> str:
    """Refresh the product's vector. Returns 'updated' or 'pending'.

    If the encoder is down the product is still saved; the stale vector (if any)
    is dropped rather than left to misrank it, and generate_embeddings.py can
    backfill later.
    """
    category = await db.scalar(select(Category.name).where(Category.category_id == product.category_id))
    row = await db.get(ProductEmbedding, product.product_id)
    try:
        vector = encode_text(build_product_text(product.name, product.description, category, product.brand))
    except EmbeddingUnavailable:
        if row is not None:
            await db.delete(row)
        return "pending"
    if row is None:
        db.add(ProductEmbedding(product_id=product.product_id, embedding=vector, model_version=settings.embedding_model))
    else:
        row.embedding = vector
        row.model_version = settings.embedding_model
    return "updated"


def _out(product: Product, embedding: str) -> dict:
    return {"product_id": str(product.product_id), "name": product.name, "embedding": embedding}


@router.post("/products", status_code=201)
async def create_product(body: ProductWrite, db: AsyncSession = Depends(get_db)):
    product = Product(**body.model_dump(exclude={"category"}), created_at=datetime.now(timezone.utc))
    if body.category:
        product.category_id = await _category_id(db, body.category)
    db.add(product)
    await db.flush()
    state = await _reembed(db, product)
    search_api._search_cache.clear()
    return _out(product, state)


@router.put("/products/{product_id}")
async def update_product(product_id: UUID, body: ProductPatch, db: AsyncSession = Depends(get_db)):
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="unknown product")
    changes = body.model_dump(exclude_unset=True)
    if "category" in changes:
        name = changes.pop("category")
        product.category_id = await _category_id(db, name) if name else None
    for key, value in changes.items():
        setattr(product, key, value)
    await db.flush()
    state = await _reembed(db, product)
    search_api._search_cache.clear()
    return _out(product, state)


@router.delete("/products/{product_id}", status_code=204)
async def delete_product(product_id: UUID, db: AsyncSession = Depends(get_db)):
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="unknown product")
    # SQLite does not enforce ON DELETE CASCADE, so remove dependents explicitly.
    row = await db.get(ProductEmbedding, product_id)
    if row is not None:
        await db.delete(row)
    await db.delete(product)
    search_api._search_cache.clear()
