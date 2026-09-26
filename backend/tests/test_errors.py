"""Error handling and response shape tests."""

from __future__ import annotations

from app.core.errors import NotFoundError
from app.main import create_app
from fastapi.testclient import TestClient


def test_unknown_route_returns_error_shape(client) -> None:
    response = client.get("/api/v1/definitely-not-a-route")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert isinstance(body["error"]["message"], str)


def test_validation_error_returns_details(client, auth_headers) -> None:
    response = client.post("/api/v1/jobs", json={}, headers=auth_headers)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert isinstance(body["error"]["details"], list)


def test_domain_error_shape(settings) -> None:
    app = create_app(settings)

    @app.get("/domain-boom")
    def _domain_boom():
        raise NotFoundError("thing 'xyz' is missing")

    with TestClient(app) as client:
        response = client.get("/domain-boom")
    assert response.status_code == 404
    body = response.json()
    assert body["error"] == {"code": "not_found", "message": "thing 'xyz' is missing"}


def test_unhandled_error_returns_500_without_leaking_internals(settings) -> None:
    app = create_app(settings)

    @app.get("/unhandled-boom")
    def _unhandled_boom():
        raise RuntimeError("internal detail that must not leak")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/unhandled-boom")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert "internal detail" not in body["error"]["message"]
