"""Embedding service — loads the sentence-transformer model and encodes text."""

import logging
from sentence_transformers import SentenceTransformer
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Module-level model singleton — loaded once at import time
_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    """Lazy-load and cache the embedding model."""
    global _model
    if _model is None:
        logger.info("Loading embedding model: %s", settings.embedding_model)
        _model = SentenceTransformer(settings.embedding_model)
        logger.info("Embedding model loaded successfully.")
    return _model


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
