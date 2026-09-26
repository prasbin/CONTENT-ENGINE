"""FastAPI dependencies (injection points for settings, auth, services)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Header, Request
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.security import AuthProvider, extract_bearer
from app.services.jobs import JobService
from app.storage.base import StorageProvider


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_auth_provider(request: Request) -> AuthProvider:
    return request.app.state.auth_provider


def get_storage(request: Request) -> StorageProvider:
    return request.app.state.storage


def get_job_service(request: Request) -> JobService:
    return request.app.state.job_service


def get_session_factory(request: Request) -> sessionmaker[Session]:
    return request.app.state.session_factory


def require_auth(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Reject requests without valid credentials (when auth is enabled)."""
    provider = get_auth_provider(request)
    provider.verify(extract_bearer(authorization))
