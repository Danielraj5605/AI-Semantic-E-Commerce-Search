"""Quick validation script — runs sample queries against existing embeddings."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.config import get_settings
from app.services.embedding_service import encode_text

settings = get_settings()


def validate():
    engine = create_engine(settings.database_url_sync)

    test_queries = [
        "comfortable running shoes for flat feet",
        "warm winter jacket for men",
        "noise cancelling headphones for work",
        "gift for a programmer",
        "healthy cooking tools",
        "pet supplies for dogs",
    ]

    with Session(engine) as session:
        # Verify embeddings exist
        count = session.execute(text("SELECT COUNT(*) FROM product_embeddings")).scalar()
        print(f"Embeddings in database: {count}\n")

        for query in test_queries:
            q_emb = encode_text(query)
            emb_str = "[" + ",".join(str(x) for x in q_emb) + "]"
            raw_sql = f"""
                SELECT p.name, p.brand, 1 - (pe.embedding <=> '{emb_str}'::vector) as similarity
                FROM product_embeddings pe
                JOIN products p ON p.product_id = pe.product_id
                ORDER BY pe.embedding <=> '{emb_str}'::vector
                LIMIT 5
            """
            results = session.execute(text(raw_sql)).fetchall()

            print(f"Query: '{query}'")
            for name, brand, sim in results:
                print(f"  {sim:.4f} — {name} ({brand})")
            print()

    engine.dispose()


if __name__ == "__main__":
    validate()
