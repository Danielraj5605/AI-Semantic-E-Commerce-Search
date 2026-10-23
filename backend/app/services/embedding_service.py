"""Embedding service — loads the sentence-transformer model and encodes text."""

import logging
import threading
import time

from sentence_transformers import SentenceTransformer
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# After a failed load, don't retry (and potentially hang on the network) for
# every request: callers get a fast EmbeddingUnavailable and fall back instead.
RETRY_AFTER_SECONDS = 60


class EmbeddingUnavailable(RuntimeError):
    """The embedding model cannot be loaded or used right now."""


# Module-level model singleton — loaded once
_model: SentenceTransformer | None = None
_failed_at: float | None = None
_lock = threading.Lock()


def _load() -> SentenceTransformer:
    # Cache first: a model already on disk must never depend on the network.
    # Hub probes can hang for minutes when offline, which used to stop the whole
    # app from starting.
    try:
        return SentenceTransformer(settings.embedding_model, local_files_only=True)
    except Exception:
        logger.info("Model not in local cache, downloading: %s", settings.embedding_model)
        return SentenceTransformer(settings.embedding_model)


def get_model() -> SentenceTransformer:
    """Lazy-load and cache the embedding model.

    Raises EmbeddingUnavailable if it cannot be loaded.
    """
    global _model, _failed_at
    if _model is not None:
        return _model
    with _lock:
        if _model is not None:
            return _model
        if _failed_at is not None and time.monotonic() - _failed_at < RETRY_AFTER_SECONDS:
            raise EmbeddingUnavailable("embedding model failed to load recently")
        try:
            logger.info("Loading embedding model: %s", settings.embedding_model)
            _model = _load()
            _failed_at = None
            logger.info("Embedding model loaded successfully.")
        except Exception as exc:
            _failed_at = time.monotonic()
            logger.error("Embedding model unavailable: %s", exc)
            raise EmbeddingUnavailable(str(exc)) from exc
    return _model


def embedding_status() -> str:
    """'ready', 'unavailable' or 'loading' (not attempted yet, or in progress)."""
    if _model is not None:
        return "ready"
    if _failed_at is not None:
        return "unavailable"
    return "loading"


def encode_text(text: str) -> list[float]:
    """Encode a single text string into a vector embedding.

    Args:
        text: The text to encode.

    Returns:
        A list of floats representing the embedding vector.
    """
    model = get_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def encode_texts(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    """Encode multiple texts into embedding vectors in batches.

    Args:
        texts: List of text strings to encode.
        batch_size: Number of texts to encode per batch.

    Returns:
        A list of embedding vectors, one per input text.
    """
    model = get_model()
    embeddings = model.encode(texts, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=True)
    return [e.tolist() for e in embeddings]


def build_product_text(name: str, description: str | None, category: str | None, brand: str | None) -> str:
    """Concatenate product fields into a single text blob for embedding.

    This combines the most semantically meaningful fields to create
    a rich representation for the embedding model.
    """
    parts = []
    if name:
        parts.append(name)
    if brand:
        parts.append(f"Brand: {brand}")
    if category:
        parts.append(f"Category: {category}")
    if description:
        parts.append(description)
    return " . ".join(parts)
