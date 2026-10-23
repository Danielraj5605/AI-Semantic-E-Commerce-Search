"""Generate embeddings for all products in the database.

This script:
1. Loads all products from the database.
2. Concatenates their text fields into a single representation.
3. Encodes them in batches using the sentence-transformer model.
4. Inserts the resulting vectors into the product_embeddings table.
5. Creates an IVFFlat index for fast similarity search.
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.config import get_settings
from app.models.models import Product, ProductEmbedding, Category
from app.services.embedding_service import encode_texts, build_product_text, get_model

settings = get_settings()


def generate_embeddings():
    """Generate and store embeddings for all products."""
    engine = create_engine(settings.database_url_sync)

    print("=" * 60)
    print("EMBEDDING GENERATION PIPELINE")
    print("=" * 60)

    # Pre-load the model
    print(f"\n1. Loading embedding model: {settings.embedding_model}")
    start = time.time()
    model = get_model()
    print(f"   Model loaded in {time.time() - start:.1f}s")
    print(f"   Embedding dimension: {settings.embedding_dimension}")

    with Session(engine) as session:
        # Load all products with their category names
        print("\n2. Loading products from database...")
        products = session.query(Product).outerjoin(Category).all()
        print(f"   Found {len(products)} products")

        if not products:
            print("   No products found! Run load_data.py first.")
            return

        # Check existing embeddings
        existing_count = session.execute(
            text("SELECT COUNT(*) FROM product_embeddings")
        ).scalar()

        if existing_count > 0:
            print(f"   Found {existing_count} existing embeddings. Clearing...")
            session.execute(text("DELETE FROM product_embeddings"))
            session.commit()

        # Build text blobs for each product
        print("\n3. Building text representations...")
        product_texts = []
        product_ids = []
        for p in products:
            # Get category name
            cat_name = None
            if p.category:
                cat_name = p.category.name

            text_blob = build_product_text(
                name=p.name,
                description=p.description,
                category=cat_name,
                brand=p.brand,
            )
            product_texts.append(text_blob)
            product_ids.append(p.product_id)

        print(f"   Sample text: {product_texts[0][:100]}...")

        # Encode in batches
        print(f"\n4. Encoding {len(product_texts)} products...")
        start = time.time()
        embeddings = encode_texts(product_texts, batch_size=32)
        elapsed = time.time() - start
        print(f"   Encoded {len(embeddings)} products in {elapsed:.1f}s")
        print(f"   Speed: {len(embeddings)/elapsed:.1f} products/sec")

        # Insert into database
        print("\n5. Storing embeddings in database...")
        start = time.time()
        for i, (pid, emb) in enumerate(zip(product_ids, embeddings)):
            pe = ProductEmbedding(
                product_id=pid,
                embedding=emb,
                model_version=settings.embedding_model,
            )
            session.add(pe)
            if (i + 1) % 50 == 0:
                session.flush()
                print(f"   Inserted {i + 1}/{len(embeddings)}...")

        session.commit()
        print(f"   Stored {len(embeddings)} embeddings in {time.time() - start:.1f}s")

        if settings.is_sqlite:
            # No pgvector locally: no index, and the validation below is pgvector SQL.
            print("\nLocal SQLite database: skipping index creation and SQL validation.")
            engine.dispose()
            return

        # Create IVFFlat index for fast similarity search
        print("\n6. Creating similarity search index...")
        # For small datasets, we need at least sqrt(n) lists
        n_lists = max(1, int(len(embeddings) ** 0.5))
        try:
            session.execute(text(
                "DROP INDEX IF EXISTS ix_product_embeddings_cosine"
            ))
            session.execute(text(
                f"CREATE INDEX ix_product_embeddings_cosine "
                f"ON product_embeddings USING ivfflat (embedding vector_cosine_ops) "
                f"WITH (lists = {n_lists})"
            ))
            session.commit()
            print(f"   IVFFlat index created with {n_lists} lists")
        except Exception as e:
            print(f"   Warning: Could not create IVFFlat index: {e}")
            print("   This is okay for small datasets; exact search will be used.")
            session.rollback()

        # Validate with a sample query
        print("\n7. Validating with sample queries...")
        test_queries = [
            "comfortable running shoes for flat feet",
            "warm winter jacket for men",
            "noise cancelling headphones for work",
            "gift for a programmer",
        ]

        from app.services.embedding_service import encode_text
        from sqlalchemy import bindparam

        for query in test_queries:
            q_emb = encode_text(query)
            emb_str = "[" + ",".join(str(x) for x in q_emb) + "]"
            # Use raw SQL with string interpolation for the vector literal
            # to avoid SQLAlchemy confusing <=> with a bind parameter
            raw_sql = f"""
                SELECT p.name, 1 - (pe.embedding <=> '{emb_str}'::vector) as similarity
                FROM product_embeddings pe
                JOIN products p ON p.product_id = pe.product_id
                ORDER BY pe.embedding <=> '{emb_str}'::vector
                LIMIT 3
            """
            results = session.execute(text(raw_sql)).fetchall()

            print(f"\n   Query: '{query}'")
            for name, sim in results:
                print(f"     {sim:.4f} — {name}")

    print("\n" + "=" * 60)
    print("EMBEDDING GENERATION COMPLETE")
    print("=" * 60)

    engine.dispose()


if __name__ == "__main__":
    generate_embeddings()
