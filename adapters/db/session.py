"""Session utilities for database access."""

from functools import lru_cache

from sqlalchemy.orm import Session, sessionmaker

from adapters.db.engine import create_db_engine


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Return the configured SQLAlchemy session factory."""
    return sessionmaker(
        bind=create_db_engine(),
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )


def new_session() -> Session:
    """Create a new database session."""
    return get_session_factory()()
