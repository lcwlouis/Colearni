"""SQLAlchemy engine configuration."""

from core.settings import Settings, get_settings
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def _validate_postgres_url(database_url: str) -> None:
    """Validate the configured DSN is PostgreSQL."""
    if not database_url.startswith(("postgresql+psycopg://", "postgresql://")):
        raise ValueError("Only PostgreSQL database URLs are supported.")


def create_db_engine(settings: Settings | None = None) -> Engine:
    """Create an application database engine."""
    active_settings = settings or get_settings()
    _validate_postgres_url(active_settings.database_url)
    return create_engine(
        active_settings.database_url,
        pool_pre_ping=True,
    )
