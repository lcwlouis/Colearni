"""Integration checks for the Postgres schema."""

import pytest
from core.settings import get_settings
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


def _connect_or_skip():
    settings = get_settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    try:
        connection = engine.connect()
    except SQLAlchemyError as exc:
        engine.dispose()
        pytest.skip(f"Postgres not available for integration test: {exc}")
    return engine, connection


def test_extensions_and_core_tables_exist() -> None:
    """Verify required extensions and key tables are present."""
    engine, connection = _connect_or_skip()
    try:
        extension_names = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT extname FROM pg_extension "
                    "WHERE extname IN ('vector', 'pg_trgm')"
                )
            )
        }
        assert {"vector", "pg_trgm"}.issubset(extension_names)

        table_names = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public' "
                    "AND tablename IN ('users', 'chunks')"
                )
            )
        }
        assert {"users", "chunks"}.issubset(table_names)
    finally:
        connection.close()
        engine.dispose()
