"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.search import router as search_router
from app.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — runs on startup and shutdown."""
    logger.info("Starting Semantic Search API...")
    logger.info("Embedding model: %s (%d dimensions)", settings.embedding_model, settings.embedding_dimension)

    # Pre-load the embedding model so the first search isn't slow
    from app.services.embedding_service import get_model
    get_model()
    logger.info("Embedding model loaded and ready.")

    yield

    logger.info("Shutting down Semantic Search API.")


app = FastAPI(
    title="Semantic E-Commerce Search API",
    description="AI-powered product search using vector embeddings and pgvector",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(search_router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "model": settings.embedding_model}
