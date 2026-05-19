from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.concepts import router as concepts_router
from .api.health import router as health_router
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
app.include_router(concepts_router)
app.include_router(tutor_router)
