"""Jobs API endpoint tests."""

from __future__ import annotations

from app.main import create_app
from fastapi.testclient import TestClient
from helpers import build_settings

VALID_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_create_job_returns_201(client, auth_headers) -> None:
    response = client.post(
        "/api/v1/jobs",
        json={"source_url": VALID_URL},
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["source_url"] == VALID_URL
    assert body["status"] == "queued"
    assert body["progress"] == 0
    assert body["error_message"] is None
    assert body["payload"] == {}


def test_create_job_with_payload(client, auth_headers) -> None:
    response = client.post(
        "/api/v1/jobs",
        json={"source_url": VALID_URL, "payload": {"niche": "mindset", "language": "en"}},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["payload"] == {"niche": "mindset", "language": "en"}


def test_create_job_rejects_invalid_urls(client, auth_headers) -> None:
    bad_urls = [
        "ftp://example.com/video.mp4",
        "javascript:alert(1)",
        "https://user:pass@example.com/video.mp4",
        "not-a-url",
        "",
    ]
    for url in bad_urls:
        response = client.post(
            "/api/v1/jobs",
            json={"source_url": url},
            headers=auth_headers,
        )
        assert response.status_code == 422, f"expected 422 for {url!r}, got {response.status_code}"
        assert response.json()["error"]["code"] == "validation_error"


def test_list_and_get_job(client, auth_headers) -> None:
    created = client.post(
        "/api/v1/jobs",
        json={"source_url": VALID_URL},
        headers=auth_headers,
    ).json()

    listed = client.get("/api/v1/jobs", headers=auth_headers)
    assert listed.status_code == 200
    listed_body = listed.json()
    assert listed_body["total"] >= 1
    assert any(item["id"] == created["id"] for item in listed_body["items"])

    fetched = client.get(f"/api/v1/jobs/{created['id']}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["id"]


def test_get_unknown_job_returns_404(client, auth_headers) -> None:
    response = client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert "00000000-0000-0000-0000-000000000000" in body["error"]["message"]


def test_patch_updates_status_and_progress(client, auth_headers) -> None:
    created = client.post(
        "/api/v1/jobs",
        json={"source_url": VALID_URL},
        headers=auth_headers,
    ).json()

    response = client.patch(
        f"/api/v1/jobs/{created['id']}",
        json={"status": "downloading", "progress": 30},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "downloading"
    assert body["progress"] == 30


def test_patch_payload_merges(client, auth_headers) -> None:
    created = client.post(
        "/api/v1/jobs",
        json={"source_url": VALID_URL},
        headers=auth_headers,
    ).json()
    job_id = created["id"]

    client.patch(f"/api/v1/jobs/{job_id}", json={"payload": {"a": 1}}, headers=auth_headers)
    second = client.patch(
        f"/api/v1/jobs/{job_id}", json={"payload": {"b": 2}}, headers=auth_headers
    )
    assert second.json()["payload"] == {"a": 1, "b": 2}


def test_patch_rejects_invalid_transition(client, auth_headers) -> None:
    created = client.post(
        "/api/v1/jobs",
        json={"source_url": VALID_URL},
        headers=auth_headers,
    ).json()

    response = client.patch(
        f"/api/v1/jobs/{created['id']}",
        json={"status": "published"},
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_status_transition"


def test_patch_rejects_out_of_range_progress(client, auth_headers) -> None:
    created = client.post(
        "/api/v1/jobs",
        json={"source_url": VALID_URL},
        headers=auth_headers,
    ).json()
    response = client.patch(
        f"/api/v1/jobs/{created['id']}",
        json={"progress": 150},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_list_rejects_unknown_status_filter(client, auth_headers) -> None:
    response = client.get("/api/v1/jobs?status=bogus", headers=auth_headers)
    assert response.status_code == 422


def test_status_filter_works(client, auth_headers) -> None:
    response = client.get("/api/v1/jobs?status=queued", headers=auth_headers)
    assert response.status_code == 200
    assert all(item["status"] == "queued" for item in response.json()["items"])


def test_jobs_survive_app_restart(tmp_path) -> None:
    settings = build_settings(tmp_path)
    with TestClient(create_app(settings)) as first_client:
        created = first_client.post(
            "/api/v1/jobs",
            json={"source_url": VALID_URL},
            headers={"Authorization": f"Bearer {settings.ce_api_token}"},
        ).json()

    # New app instance + new engine against the same database file.
    with TestClient(create_app(settings)) as second_client:
        response = second_client.get(
            f"/api/v1/jobs/{created['id']}",
            headers={"Authorization": f"Bearer {settings.ce_api_token}"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "queued"


def test_invalid_json_body_returns_validation_error(client, auth_headers) -> None:
    response = client.post(
        "/api/v1/jobs",
        json={"payload": {"missing": "url"}},
        headers=auth_headers,
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["details"] is not None
