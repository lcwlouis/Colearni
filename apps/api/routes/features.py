"""Feature flags endpoint."""

from core.settings import Settings
from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/settings", tags=["settings"])


class FeatureFlagsResponse(BaseModel):
    socratic_mode_default: bool
    include_dev_stats: bool


@router.get("/features", response_model=FeatureFlagsResponse)
def get_feature_flags(request: Request) -> FeatureFlagsResponse:
    settings_state = getattr(request.app.state, "settings", None)
    settings = settings_state if isinstance(settings_state, Settings) else Settings()
    return FeatureFlagsResponse(
        socratic_mode_default=settings.socratic_mode_default,
        include_dev_stats=settings.include_dev_stats,
    )
