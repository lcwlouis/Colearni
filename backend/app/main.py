import importlib.util
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .api.concepts import concept_sources_router
from .api.concepts import router as concepts_router
from .api.health import router as health_router
from .api.sources import router as sources_router
from .api.trail_packs import router as trail_packs_router
from .api.trails import router as trails_router
from .api.tutor import router as tutor_router
from .api.workspaces import router as workspaces_router
from .db import AsyncSessionLocal, engine
from .logging_config import configure_logging
from .services.workspaces import ensure_default_workspace
from .settings import settings

# Uvicorn configures its own loggers, so backend package logs need explicit wiring.
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    # Validate pgvector adapter and database extension for source chunk embeddings.
    # Remove only if embedding storage no longer uses PostgreSQL vector columns.
    await _ensure_pgvector_available()

    # Ensure a default workspace exists for local-ready single-user mode.
    # Replace with user-scoped workspace provisioning when auth is added.
    async with AsyncSessionLocal() as session:
        await ensure_default_workspace(session)

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    # Close all pooled DB connections cleanly so PostgreSQL doesn't see them
    # as abruptly dropped. Add teardown for any new resources (HTTP clients,
    # caches, background workers) directly below this line.
    await engine.dispose()


async def _ensure_pgvector_available() -> None:
    if not settings.database_url.startswith("postgresql"):
        return

    if importlib.util.find_spec("pgvector") is None:
        raise RuntimeError(
            "Python package 'pgvector' is required when using PostgreSQL vector columns. "
            "Install backend dependencies with `uv sync --extra dev` or `pip install -e .`."
        )

    async with engine.begin() as conn:
        extension_available = await conn.scalar(
            text("select exists(select 1 from pg_available_extensions where name = 'vector')")
        )
        if not extension_available:
            raise RuntimeError(
                "PostgreSQL extension 'vector' is not available. Install pgvector in the "
                "database server, then rerun migrations."
            )
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


app = FastAPI(
    title="CoLearni API",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(workspaces_router)
app.include_router(trails_router)
app.include_router(sources_router)
app.include_router(trail_packs_router)
app.include_router(concept_sources_router)
app.include_router(concepts_router)
app.include_router(tutor_router)
