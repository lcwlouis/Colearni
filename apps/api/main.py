"""FastAPI app entrypoint."""

from core.settings import get_settings
from fastapi import FastAPI

from apps.api.routes.chat import router as chat_router
from apps.api.routes.documents import router as documents_router
from apps.api.routes.healthz import router as healthz_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI app."""
    settings = get_settings()
    app = FastAPI(title="Colearni API", version="0.1.0")
    app.state.settings = settings
    app.include_router(healthz_router)
    app.include_router(chat_router)
    app.include_router(documents_router)
    return app


app = create_app()
