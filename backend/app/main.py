"""FastAPI application entry point."""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from fastapi.middleware.cors import CORSMiddleware

from app.api.search import router as search_router
from app.config import get_settings
from app.db.session import async_session

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

    # Warm the embedding model in the background. The API must come up even if
    # the model cannot load; search then degrades to keyword (FR6 / NFR4).
    from app.services.embedding_service import get_model, EmbeddingUnavailable

    def _warm():
        try:
            get_model()
        except EmbeddingUnavailable:
            logger.warning("Starting without embeddings; search will use keyword fallback.")

    threading.Thread(target=_warm, name="embedding-warmup", daemon=True).start()

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


@app.exception_handler(SQLAlchemyError)
@app.exception_handler(ConnectionError)
async def database_unavailable(request: Request, exc: Exception):
    """A dead database is a 503 the UI can explain, not an opaque 500."""
    logger.error("Database error on %s: %s", request.url.path, exc)
    return JSONResponse(status_code=503, content={"detail": "database unavailable"})


@app.get("/health")
async def health_check():
    """Report real component state; 503 only when the database is unreachable."""
    from app.services.embedding_service import embedding_status

    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        database = "ok"
    except Exception as exc:
        logger.error("Health check: database down: %s", exc)
        database = "down"

    embeddings = embedding_status()
    body = {
        "status": "ok" if database == "ok" and embeddings == "ready" else "degraded",
        "model": settings.embedding_model,
        "embeddings": embeddings,
        "database": database,
    }
    return JSONResponse(status_code=200 if database == "ok" else 503, content=body)
