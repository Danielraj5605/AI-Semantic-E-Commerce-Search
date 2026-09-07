"""Database migration script — creates all tables and enables pgvector."""

import sys
import os

# Add the backend directory to path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, text
from app.config import get_settings
from app.db.session import Base
from app.models.models import (
    Category, Product, ProductImage, User, SearchLog, ProductEmbedding,
)

settings = get_settings()


def run_migrations():
    """Create all tables in the database."""
    print("Connecting to database...")
    engine = create_engine(settings.database_url_sync, echo=True)

    with engine.connect() as conn:
        # Enable pgvector extension
        print("Enabling pgvector extension...")
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
        print("pgvector extension enabled.")

    # Create all tables
    print("Creating tables...")
    Base.metadata.create_all(engine)
    print("All tables created successfully!")

    # Verify tables
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        ))
        tables = [row[0] for row in result]
        print(f"\nTables in database: {tables}")

    engine.dispose()


if __name__ == "__main__":
    run_migrations()
