"""Application startup and health endpoint tests."""

from __future__ import annotations

from app import __version__
from fastapi import FastAPI


def test_app_starts_with_expected_metadata(app: FastAPI) -> None:
    assert app.title == "CONTENT ENGINE API"
    assert app.version == __version__


def test_health_endpoint_is_public_and_ok(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["service"] == "content-engine"
    assert body["env"] == "testing"
    assert body["version"] == __version__
    assert body["time"].endswith(("Z", "+00:00"))


def test_versioned_health_endpoint_exists(client) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_openapi_schema_lists_jobs_routes(client) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/jobs" in paths
    assert "/health" in paths
