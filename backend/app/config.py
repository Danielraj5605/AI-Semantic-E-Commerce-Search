"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Database
    database_url: str = "postgresql+asyncpg://localhost/neondb"
    database_url_sync: str = "postgresql+psycopg2://localhost/neondb"

    # Embedding model
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # Search defaults
    default_search_limit: int = 20
    max_search_limit: int = 100
    cache_ttl_seconds: int = 300  # 5 minute cache
    cache_max_size: int = 512

    # CORS
    frontend_url: str = "http://localhost:5173"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings singleton."""
    return Settings()
