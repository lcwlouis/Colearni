"""Health check route definitions."""

from core.health import get_health_payload
from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Return a simple liveness payload."""
    return get_health_payload()
