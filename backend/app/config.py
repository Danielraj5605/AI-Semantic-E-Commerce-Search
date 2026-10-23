"""Application configuration loaded from environment variables."""

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings
from functools import lru_cache

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Database
    database_url: str = "postgresql+asyncpg://localhost/neondb"
    database_url_sync: str = "postgresql+psycopg2://localhost/neondb"

    # Local fallback: when true, both URLs are replaced with a SQLite file in
    # backend/, so the app runs without Neon/Postgres. pgvector is unavailable
    # there, so embeddings are stored as JSON and ranked in Python.
    use_local_db: bool = False
    local_db_path: str = "catalogue.db"

    # Embedding model
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # Search defaults
    default_search_limit: int = 20
    max_search_limit: int = 100

    # Minimum cosine similarity for a product to count as a result at all.
    # Without a floor, nearest-neighbour search ranks the *entire* catalogue and
    # returns all of it — including negative-similarity items — so unrelated
    # products surface whenever few things genuinely match the query.
    # 0.25 was chosen from the observed distribution of all-MiniLM-L6-v2 on this
    # catalogue: direct answers land 0.50-0.65, merely-related 0.32-0.50, and
    # noise below 0.30. Re-tune if the model or the catalogue changes.
    min_similarity: float = 0.25
    cache_ttl_seconds: int = 300  # 5 minute cache
    cache_max_size: int = 512

    # Namespace for minted resource URIs (products, brands). The default matches
    # the frontend. Set it to this API's own address, e.g. http://localhost:8000/api/,
    # and every product URI becomes dereferenceable via /api/product/{id}.
    base_uri: str = "http://example.org/catalog/"

    # Admin write endpoints are mounted only when a token is set. Empty = disabled.
    admin_token: str = ""

    # CORS
    frontend_url: str = "http://localhost:5173"

    @model_validator(mode="after")
    def _apply_local_db(self) -> "Settings":
        if self.use_local_db:
            path = (BACKEND_DIR / self.local_db_path).as_posix()
            self.database_url = f"sqlite+aiosqlite:///{path}"
            self.database_url_sync = f"sqlite:///{path}"
        return self

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings singleton."""
    return Settings()
