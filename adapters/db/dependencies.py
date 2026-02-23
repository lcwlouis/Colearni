"""FastAPI dependencies for database access."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from adapters.db.session import new_session


def get_db_session() -> Generator[Session, None, None]:
    """Yield a database session and guarantee cleanup."""
    session = new_session()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
