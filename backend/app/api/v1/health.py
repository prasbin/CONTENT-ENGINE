"""Health endpoints (public: no authentication required)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app import __version__
from app.db.session import check_database
from app.models.job import utcnow
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Service health")
def health(request: Request) -> HealthResponse:
    engine = getattr(request.app.state, "engine", None)
    database_ok = check_database(engine)
    settings = request.app.state.settings
    return HealthResponse(
        status="ok" if database_ok else "degraded",
        service="content-engine",
        version=__version__,
        env=settings.app_env,
        database="ok" if database_ok else "error",
        time=utcnow(),
    )
