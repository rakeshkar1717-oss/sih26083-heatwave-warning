"""Database session and engine management for SIH26083.

Provides connection pooling, session lifecycle management, and
database initialization for SQLite (local default) and PostgreSQL/PostGIS (production).
"""

from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from backend.config import settings, PROCESSED_DATA_DIR
from backend.db.models_orm import Base


# Ensure local database directory exists if using SQLite file
if "sqlite" in settings.database_url:
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False}
else:
    connect_args = {}

# Primary SQLAlchemy Engine
engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=False,
    future=True,
)

# Thread-local Session Factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding an isolated database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(engine_instance=None) -> None:
    """Create all relational tables in the database."""
    target_engine = engine_instance or engine
    Base.metadata.create_all(bind=target_engine)
