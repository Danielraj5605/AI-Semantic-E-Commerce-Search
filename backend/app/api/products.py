"""Per-product routes: Linked Data publishing and "find similar"."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.schemas import ProductOut, SearchResponse
from app.services import rdf_service
from app.services.search_service import get_product_row, similar_products

router = APIRouter(prefix="/api", tags=["products"])


@router.get("/product/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: UUID,
    format: Optional[str] = Query(None, description="ttl | rdf | xml | jsonld | json — overrides Accept"),
    accept: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """One product, by content negotiation.

    `Accept: text/turtle`, `application/rdf+xml` or `application/ld+json` returns
    the product's RDF description; anything else returns JSON. Set BASE_URI to
    this API's address and the product's URI is the URL you just fetched.
    """
    try:
        media_type = rdf_service.negotiate(accept, format)
    except ValueError as err:
        raise HTTPException(status_code=406, detail=str(err))

    product = await get_product_row(db, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="unknown product")

    if media_type is None:
        return product
    graph = rdf_service.product_graph(product)
    return Response(
        content=rdf_service.serialise(graph, media_type),
        media_type=media_type,
        headers={"Vary": "Accept"},
    )


@router.get("/product/{product_id}/similar", response_model=SearchResponse)
async def similar(
    product_id: UUID,
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    min_similarity: Optional[float] = Query(None, ge=0, le=1),
    db: AsyncSession = Depends(get_db),
):
    """Products nearest to this one by stored embedding (works with the model down)."""
    found = await similar_products(db, product_id, limit, offset, min_similarity)
    if found is None:
        raise HTTPException(status_code=404, detail="unknown product or no embedding yet")
    seed, results, total = found
    return SearchResponse(query=seed["name"], total=total, results=results, search_type="semantic")
