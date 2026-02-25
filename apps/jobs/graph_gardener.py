"""Bounded one-run utility for offline graph gardener consolidation."""

from __future__ import annotations

import argparse

from adapters.db.session import new_session
from adapters.llm.factory import build_graph_llm_client
from core.settings import get_settings
from domain.graph.gardener import run_graph_gardener


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one bounded graph gardener pass")
    parser.add_argument("--workspace-id", type=int, required=True, help="Workspace id")
    parser.add_argument(
        "--max-dirty-nodes",
        type=int,
        default=None,
        help="Optional override cap for selected dirty/recent seed nodes",
    )
    parser.add_argument(
        "--max-clusters",
        type=int,
        default=None,
        help="Optional override cap for clusters processed in this run",
    )
    parser.add_argument(
        "--max-llm-calls",
        type=int,
        default=None,
        help="Optional override cap for LLM calls in this run",
    )
    return parser.parse_args()


def main() -> int:
    """Run one bounded graph gardener pass and print a short summary."""
    args = _parse_args()
    settings = get_settings()
    llm_client = build_graph_llm_client(settings=settings)

    session = new_session()
    try:
        result = run_graph_gardener(
            session,
            workspace_id=args.workspace_id,
            llm_client=llm_client,
            settings=settings,
            max_dirty_nodes=args.max_dirty_nodes,
            max_clusters=args.max_clusters,
            max_llm_calls=args.max_llm_calls,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    print(
        "Gardener complete: "
        f"seed_nodes_selected={result.seed_nodes_selected} "
        f"clusters_total={result.clusters_total} "
        f"clusters_processed={result.clusters_processed} "
        f"clusters_skipped={result.clusters_skipped} "
        f"merges_applied={result.merges_applied} "
        f"llm_calls={result.llm_calls} "
        f"stopped_by_cluster_budget={result.stopped_by_cluster_budget} "
        f"stopped_by_llm_budget={result.stopped_by_llm_budget}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
