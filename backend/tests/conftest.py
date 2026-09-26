"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.core.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient
from helpers import build_settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return build_settings(tmp_path)


@pytest.fixture
def auth_headers(settings: Settings) -> dict[str, str]:
    assert settings.ce_api_token is not None
    return {"Authorization": f"Bearer {settings.ce_api_token}"}


@pytest.fixture
def app(settings: Settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client
