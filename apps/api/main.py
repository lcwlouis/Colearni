"""FastAPI app entrypoint."""

from adapters.llm.factory import build_graph_llm_client
from core.settings import Settings, get_settings
from fastapi import FastAPI

from apps.api.routes.chat import router as chat_router
from apps.api.routes.documents import router as documents_router
from apps.api.routes.healthz import router as healthz_router
from apps.api.routes.practice import router as practice_router
from apps.api.routes.quizzes import router as quizzes_router


def create_app(*, settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI app."""
    resolved_settings = settings if settings is not None else get_settings()
    app = FastAPI(title="Colearni API", version="0.1.0")
    app.state.settings = resolved_settings
    app.state.graph_llm_client = (
        build_graph_llm_client(settings=resolved_settings)
        if resolved_settings.ingest_build_graph
        else None
    )
    app.state.graph_embedding_provider = None
    app.include_router(healthz_router)
    app.include_router(chat_router)
    app.include_router(documents_router)
    app.include_router(quizzes_router)
    app.include_router(practice_router)
    return app


app = create_app()
