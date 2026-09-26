"""Authentication behavior tests."""

from __future__ import annotations

import pytest
from app.core.errors import AuthenticationError
from app.core.security import TokenAuthProvider, build_auth_provider, extract_bearer
from app.main import create_app
from fastapi.testclient import TestClient
from helpers import build_settings

JOB_URL = "https://example.com/video.mp4"


def _create(client: TestClient, headers: dict[str, str] | None = None):
    return client.post("/api/v1/jobs", json={"source_url": JOB_URL}, headers=headers or {})


def test_auth_disabled_when_no_token_configured(tmp_path) -> None:
    settings = build_settings(tmp_path, ce_api_token=None)
    with TestClient(create_app(settings)) as client:
        response = _create(client)
        assert response.status_code == 201


def test_missing_token_rejected(client) -> None:
    response = _create(client)
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "unauthorized"
    assert body["error"]["message"] == "missing bearer token"


def test_wrong_token_rejected(client, auth_headers) -> None:
    wrong = {"Authorization": "Bearer wrong-token"}
    response = _create(client, wrong)
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "invalid bearer token"


def test_malformed_authorization_header_rejected(client) -> None:
    response = _create(client, {"Authorization": "Token abc123"})
    assert response.status_code == 401
    assert "Bearer" in response.json()["error"]["message"]


def test_valid_token_accepted(client, auth_headers) -> None:
    response = _create(client, auth_headers)
    assert response.status_code == 201


def test_health_stays_open_without_token(client) -> None:
    assert client.get("/health").status_code == 200


def test_extract_bearer_variants() -> None:
    assert extract_bearer(None) is None
    assert extract_bearer("Bearer abc.def") == "abc.def"
    with pytest.raises(AuthenticationError):
        extract_bearer("Basic YWJj")


def test_token_auth_provider_verify() -> None:
    provider = TokenAuthProvider("s3cret-token")
    assert provider.verify("s3cret-token") is None
    with pytest.raises(AuthenticationError):
        provider.verify(None)
    with pytest.raises(AuthenticationError):
        provider.verify("other")


def test_token_auth_provider_rejects_empty_token() -> None:
    with pytest.raises(ValueError):
        TokenAuthProvider("")


def test_build_auth_provider_selection(settings, tmp_path) -> None:
    assert isinstance(build_auth_provider(settings), TokenAuthProvider)
    open_settings = build_settings(tmp_path, ce_api_token=None)
    provider = build_auth_provider(open_settings)
    assert provider.verify(None) is None  # development-only provider
