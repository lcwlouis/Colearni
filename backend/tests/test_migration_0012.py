"""Migration test for 0012_trail_prior_knowledge: applies and reverses cleanly."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def _load_migration():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0012_trail_prior_knowledge.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0012", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(module)
    return module


def test_migration_0012_revision_id_fits_varchar_32():
    migration = _load_migration()
    assert len(migration.revision) <= 32
    assert migration.down_revision == "0011_source_chunks"


def test_migration_0012_adds_and_drops_prior_knowledge():
    engine = create_engine("sqlite://")
    migration = _load_migration()

    with engine.connect() as conn:
        conn.execute(sa.text("CREATE TABLE trails (id TEXT PRIMARY KEY, title TEXT)"))
        ctx = MigrationContext.configure(conn)
        # The migration module references the global `op` proxy; bind it to a
        # concrete Operations instance for this isolated connection.
        setattr(migration, "op", Operations(ctx))

        migration.upgrade()
        columns = {col["name"] for col in inspect(conn).get_columns("trails")}
        assert "prior_knowledge" in columns

        migration.downgrade()
        columns = {col["name"] for col in inspect(conn).get_columns("trails")}
        assert "prior_knowledge" not in columns
