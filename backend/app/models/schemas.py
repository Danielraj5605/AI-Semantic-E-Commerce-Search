"""Pydantic schemas for API request/response validation."""

from typing import Optional, List
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime


# ---------- Category ----------

class CategoryOut(BaseModel):
    category_id: int
    name: str
    parent_category_id: Optional[int] = None

    model_config = {"from_attributes": True}


# ---------- Product ----------

class ProductOut(BaseModel):
    """Product data returned in search results."""
    product_id: UUID
    name: str
    description: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    brand: Optional[str] = None
    price: Optional[float] = None
    stock_quantity: int = 0
    rating_avg: float = 0.0
    image_url: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---------- Search ----------

class SearchRequest(BaseModel):
    """Search query parameters."""
    query: str = Field(..., min_length=1, max_length=500)
    category: Optional[str] = None
    brand: Optional[str] = None
    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = Field(None, ge=0)
    min_rating: Optional[float] = Field(None, ge=0, le=5)
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


class SearchResult(BaseModel):
    """Single search result with relevance score."""
    product: ProductOut
    score: float = Field(..., description="Similarity score (higher = more relevant)")


class SearchResponse(BaseModel):
    """Paginated search results."""
    query: str
    total: int
    results: List[SearchResult]
    search_type: str = "semantic"  # "semantic" or "keyword"


# ---------- Autocomplete ----------

class AutocompleteResponse(BaseModel):
    suggestions: List[str]


# ---------- Filters ----------

class FilterOptions(BaseModel):
    """Available filter values for the frontend sidebar."""
    categories: List[CategoryOut]
    brands: List[str]
    price_range: dict  # {"min": float, "max": float}
