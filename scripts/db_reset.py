#!/usr/bin/env python3
"""Reset the database: drop all tables, re-run migrations.

Usage:
    python -m scripts.db_reset          # interactive confirmation
    python -m scripts.db_reset --yes    # skip confirmation (CI / dev)
"""

from __future__ import annotations

import argparse
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from adapters.db.engine import create_db_engine


def _drop_all(engine) -> None:  # type: ignore[no-untyped-def]
    """Drop every table, enum, and extension (pgvector) in public schema."""
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO public"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset the database.")
    parser.add_argument(
        "--yes", "-y", action="store_true", help="Skip confirmation prompt."
    )
    args = parser.parse_args()

    engine = create_db_engine()

    if not args.yes:
        answer = input(
            f"⚠️  This will DROP ALL TABLES in {engine.url}. Continue? [y/N] "
        )
        if answer.strip().lower() not in ("y", "yes"):
            print("Aborted.")
            sys.exit(0)

    print(f"Dropping all tables in {engine.url} …")
    _drop_all(engine)
    engine.dispose()

    print("Running alembic upgrade head …")
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

    print("✅ Database reset complete.")


if __name__ == "__main__":
    main()
