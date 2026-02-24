"""Bounded one-run utility for chunk embedding backfill."""

from __future__ import annotations

import argparse

from adapters.db.session import new_session
from adapters.embeddings.factory import build_embedding_provider
from core.settings import get_settings
from domain.embeddings.pipeline import backfill_missing_chunk_embeddings


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill missing chunk embeddings")
    parser.add_argument("--workspace-id", type=int, default=None, help="Optional workspace filter")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max rows to process this run (capped by APP_EMBEDDING_BACKFILL_MAX_CHUNKS)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Optional override for APP_EMBEDDING_BATCH_SIZE",
    )
    return parser.parse_args()


def main() -> int:
    """Run one bounded embedding backfill pass and print a short summary."""
    args = _parse_args()
    settings = get_settings()

    provider = build_embedding_provider(settings=settings)
    batch_size = settings.embedding_batch_size if args.batch_size is None else args.batch_size

    session = new_session()
    try:
        result = backfill_missing_chunk_embeddings(
            session=session,
            provider=provider,
            workspace_id=args.workspace_id,
            requested_limit=args.limit,
            max_chunks=settings.embedding_backfill_max_chunks,
            batch_size=batch_size,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    print(
        "Backfill complete: "
        f"requested_limit={result.requested_limit} "
        f"effective_limit={result.effective_limit} "
        f"candidate_chunks={result.candidate_chunks} "
        f"updated_chunks={result.updated_chunks}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
