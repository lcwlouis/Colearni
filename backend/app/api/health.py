from typing import Literal

import asyncpg
from fastapi import APIRouter
from pydantic import BaseModel

from ..settings import settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    db: Literal["ok", "error"]


async def _check_db() -> Literal["ok", "error"]:
    try:
        conn = await asyncpg.connect(
            settings.database_url.replace("postgresql+asyncpg://", "postgresql://"),
            timeout=3,
        )
        await conn.fetchval("SELECT 1")
        await conn.close()
        return "ok"
    except Exception:
        return "error"


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    db_status = await _check_db()
    return HealthResponse(version=settings.app_version, db=db_status)
