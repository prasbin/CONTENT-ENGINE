"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging
from app.core.security import build_auth_provider
from app.db.session import (
    create_engine_from_url,
    create_session_factory,
    init_db,
)
from app.providers.registry import build_default_registry
from app.services.jobs import JobService
from app.storage.local import LocalStorage

logger = logging.getLogger("content_engine")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the CONTENT ENGINE API application.

    Pure construction: no filesystem/database side effects happen until
    the lifespan runs (i.e. when the server or test client starts).
    """
    resolved = settings if settings is not None else get_settings()
    setup_logging(resolved.ce_log_level, json_logs=resolved.is_production)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine_from_url(resolved.ce_database_url)
        init_db(engine)
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        app.state.job_service = JobService(app.state.session_factory)
        logger.info(
            "startup: env=%s db_backend=%s auth=%s",
            resolved.app_env,
            _db_backend(resolved.ce_database_url),
            "enabled" if resolved.auth_enabled else "DISABLED (development only)",
        )
        yield
        engine.dispose()
        logger.info("shutdown: database engine disposed")

    app = FastAPI(
        title="CONTENT ENGINE API",
        version=__version__,
        description="Automated short-video content pipeline API.",
        lifespan=lifespan,
    )
    app.state.settings = resolved
    app.state.auth_provider = build_auth_provider(resolved)
    app.state.storage = LocalStorage(root=resolved.ce_storage_path)
    app.state.providers = build_default_registry(storage=app.state.storage)

    if not resolved.auth_enabled and resolved.is_production:
        logger.warning("CE_API_TOKEN is empty while APP_ENV=production - auth is disabled")

    register_exception_handlers(app)

    if resolved.ce_cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=resolved.cors_origin_list,
            allow_credentials="*" not in resolved.ce_cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(health_router)
    app.include_router(api_router, prefix="/api/v1")
    return app


def _db_backend(database_url: str) -> str:
    from sqlalchemy.engine import make_url

    return make_url(database_url).get_backend_name()


app = create_app()
