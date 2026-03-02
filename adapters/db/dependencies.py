"""FastAPI dependencies for database access."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from adapters.db.session import new_session


def get_db_session() -> Generator[Session, None, None]:
    """Yield a database session and guarantee cleanup.

    Commits on clean exit so route handlers that perform mutations
    through domain services don't need explicit ``session.commit()``
    calls.  Any exception triggers a rollback instead.
    """
    session = new_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
