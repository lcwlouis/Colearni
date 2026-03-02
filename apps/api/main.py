"""FastAPI app entrypoint."""

import logging

from adapters.llm.factory import build_graph_llm_client
from core.observability import configure_observability
from core.settings import Settings, get_settings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.middleware import CorrelationIdMiddleware
from apps.api.routes.auth import router as auth_router
from apps.api.routes.chat import router as chat_router
from apps.api.routes.documents import router as documents_router
from apps.api.routes.features import router as features_router
from apps.api.routes.graph import router as graph_router
from apps.api.routes.healthz import router as healthz_router
from apps.api.routes.knowledge_base import router as knowledge_base_router
from apps.api.routes.onboarding import router as onboarding_router
from apps.api.routes.practice import router as practice_router
from apps.api.routes.quizzes import router as quizzes_router
from apps.api.routes.readiness import router as readiness_router
from apps.api.routes.research import router as research_router
from apps.api.routes.workspaces import router as workspaces_router


def create_app(*, settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI app."""
    resolved_settings = settings if settings is not None else get_settings()

    # F4: Configure root log level from APP_LOG_LEVEL env var
    logging.basicConfig(
        level=getattr(logging, resolved_settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )

    configure_observability(resolved_settings)
    app = FastAPI(title="CoLearni API", version="0.1.0", redirect_slashes=False)
    app.state.settings = resolved_settings
    app.state.graph_llm_client = (
        build_graph_llm_client(settings=resolved_settings)
        if resolved_settings.ingest_build_graph
        else None
    )
    app.state.graph_embedding_provider = None

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_allowed_origins,
        allow_methods=resolved_settings.cors_allowed_methods,
        allow_credentials=True,
        allow_headers=["*"],
    )
    app.add_middleware(CorrelationIdMiddleware)

    app.include_router(healthz_router)
    app.include_router(auth_router)
    app.include_router(features_router)
    app.include_router(workspaces_router)
    app.include_router(chat_router)
    app.include_router(documents_router)
    app.include_router(graph_router)
    app.include_router(knowledge_base_router)
    app.include_router(onboarding_router)
    app.include_router(quizzes_router)
    app.include_router(practice_router)
    app.include_router(readiness_router)
    app.include_router(research_router)
    return app


app = create_app()
