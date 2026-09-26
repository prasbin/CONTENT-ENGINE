"""Shared schema fragments."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str = Field(description="Stable machine-readable error code")
    message: str = Field(description="Human-readable error message")
    details: Any | None = Field(default=None, description="Optional extra context")


class ErrorResponse(BaseModel):
    error: ErrorBody
