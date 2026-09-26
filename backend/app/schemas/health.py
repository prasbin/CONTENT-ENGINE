"""Health check schema."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    version: str
    env: str
    database: Literal["ok", "error"]
    time: datetime = Field(description="Server time in UTC")
