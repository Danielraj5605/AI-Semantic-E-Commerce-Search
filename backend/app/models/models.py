"""SQLAlchemy ORM models matching the database schema (Section 5 of the plan)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Text, Float, Numeric,
    DateTime, ForeignKey, Index, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.db.session import Base
from app.config import get_settings

settings = get_settings()


class Category(Base):
    """Product category with optional parent for hierarchical categorization."""
    __tablename__ = "categories"

    category_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    parent_category_id = Column(
        Integer,
        ForeignKey("categories.category_id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    parent = relationship("Category", remote_side=[category_id], backref="subcategories")
    products = relationship("Product", back_populates="category")


class Product(Base):
    """Core product table with all catalog fields."""
    __tablename__ = "products"

    product_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    category_id = Column(
        Integer,
        ForeignKey("categories.category_id", ondelete="SET NULL"),
        nullable=True,
    )
    brand = Column(String(255), nullable=True)
    price = Column(Numeric(10, 2), nullable=True)
    stock_quantity = Column(Integer, default=0)
    rating_avg = Column(Float, default=0.0)
    image_url = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    category = relationship("Category", back_populates="products")
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")
    embedding = relationship(
        "ProductEmbedding", back_populates="product", uselist=False, cascade="all, delete-orphan"
    )

    # Indexes for filtered columns
    __table_args__ = (
        Index("ix_products_category_id", "category_id"),
        Index("ix_products_brand", "brand"),
        Index("ix_products_price", "price"),
        Index("ix_products_rating_avg", "rating_avg"),
    )


class ProductImage(Base):
    """Additional product images."""
    __tablename__ = "product_images"

    image_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("products.product_id", ondelete="CASCADE"),
        nullable=False,
    )
    image_url = Column(Text, nullable=False)

    # Relationships
    product = relationship("Product", back_populates="images")


class User(Base):
    """User accounts for personalization and search logging."""
    __tablename__ = "users"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)

    # Relationships
    search_logs = relationship("SearchLog", back_populates="user")


class SearchLog(Base):
    """Log of search queries for analytics and evaluation."""
    __tablename__ = "search_logs"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    query_text = Column(Text, nullable=False)
    clicked_product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("products.product_id", ondelete="SET NULL"),
        nullable=True,
    )
    timestamp = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    user = relationship("User", back_populates="search_logs")


class ProductEmbedding(Base):
    """Vector embeddings for semantic search via pgvector."""
    __tablename__ = "product_embeddings"

    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("products.product_id", ondelete="CASCADE"),
        primary_key=True,
    )
    embedding = Column(Vector(settings.embedding_dimension), nullable=False)
    model_version = Column(String(100), nullable=False, default="all-MiniLM-L6-v2")

    # Relationships
    product = relationship("Product", back_populates="embedding")
