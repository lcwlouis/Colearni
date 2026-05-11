from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.health import router as health_router
from .settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="CoLearni API",
    version=settings.app_version,
    lifespan=lifespan,
)

app.include_router(health_router)
