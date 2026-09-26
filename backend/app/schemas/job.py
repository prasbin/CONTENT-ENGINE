"""Job request/response schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.job import JobStatus

MAX_SOURCE_URL_LENGTH = 2048
MAX_ERROR_MESSAGE_LENGTH = 4000


def validate_source_url(value: str) -> str:
    """Allow only sanitized http(s) URLs without embedded credentials."""
    if not value or not value.strip():
        raise ValueError("source_url must not be empty")
    value = value.strip()
    if len(value) > MAX_SOURCE_URL_LENGTH:
        raise ValueError(f"source_url must be at most {MAX_SOURCE_URL_LENGTH} characters")
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("source_url must use http:// or https://")
    if not parsed.netloc:
        raise ValueError("source_url is missing a host")
    if parsed.username or parsed.password:
        raise ValueError("source_url must not contain embedded credentials")
    return value


def _as_utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes; normalize them to aware UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class JobCreate(BaseModel):
    """Payload for creating a new job."""

    source_url: str = Field(description="Video URL to process")
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional job configuration/metadata (niche, language, ...)",
    )

    @field_validator("source_url")
    @classmethod
    def _check_source_url(cls, value: str) -> str:
        return validate_source_url(value)


class JobUpdate(BaseModel):
    """Partial update for an existing job (used by API clients and workers)."""

    status: JobStatus | None = None
    progress: int | None = Field(default=None, ge=0, le=100)
    error_message: str | None = Field(default=None, max_length=MAX_ERROR_MESSAGE_LENGTH)
    payload: dict[str, Any] | None = Field(
        default=None, description="Shallow-merged into the existing payload"
    )


class JobRead(BaseModel):
    """Serialized job."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    source_url: str
    status: JobStatus
    progress: int
    error_message: str | None
    payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def _ensure_aware(cls, value: datetime) -> datetime:
        return _as_utc(value)


class JobList(BaseModel):
    items: list[JobRead]
    total: int
