"""Tests for pipeline state transitions and storage download path traversal."""

from __future__ import annotations

from app.core.config import Settings
from app.db.session import create_engine_from_url, create_session_factory, init_db
from app.main import create_app
from app.models.job import JobStatus, can_transition
from app.services.jobs import JobService
from fastapi.testclient import TestClient
from helpers import TEST_TOKEN

# ---------------------------------------------------------------------------
# Pipeline state transitions
# ---------------------------------------------------------------------------


def test_pipeline_forward_transitions_are_legal() -> None:
    """Each consecutive stage in PIPELINE_ORDER must transition forward."""
    from app.models.job import PIPELINE_ORDER

    for i in range(len(PIPELINE_ORDER) - 1):
        assert can_transition(PIPELINE_ORDER[i], PIPELINE_ORDER[i + 1]), (
            f"cannot advance {PIPELINE_ORDER[i]} -> {PIPELINE_ORDER[i + 1]}"
        )


def test_pipeline_skipping_forward_is_illegal() -> None:
    assert can_transition(JobStatus.TRANSCRIBING, JobStatus.RENDERING) is False
    assert can_transition(JobStatus.DOWNLOADING, JobStatus.REVIEW) is False


def test_any_stage_can_fail() -> None:
    for status in (
        JobStatus.QUEUED,
        JobStatus.DOWNLOADING,
        JobStatus.TRANSCRIBING,
        JobStatus.RENDERING,
        JobStatus.REVIEW,
    ):
        assert can_transition(status, JobStatus.FAILED) is True


def test_failed_can_retry_to_queued_only() -> None:
    assert can_transition(JobStatus.FAILED, JobStatus.QUEUED) is True
    assert can_transition(JobStatus.FAILED, JobStatus.DOWNLOADING) is False


def test_review_can_rerender() -> None:
    assert can_transition(JobStatus.REVIEW, JobStatus.RENDERING) is True


def test_recover_pipeline_jobs_requeues_stuck_stages(settings: Settings) -> None:
    engine = create_engine_from_url(settings.ce_database_url)
    init_db(engine)
    service = JobService(create_session_factory(engine))
    try:
        # Simulate jobs stuck in mid-pipeline stages.
        job_t = service.create(source_url="https://example.com/t.mp4")
        service.update(job_t.id, __import__("app.schemas.job", fromlist=["JobUpdate"]).JobUpdate(
            status=JobStatus.DOWNLOADING
        ))
        service.update(job_t.id, __import__("app.schemas.job", fromlist=["JobUpdate"]).JobUpdate(
            status=JobStatus.TRANSCRIBING
        ))

        job_r = service.create(source_url="https://example.com/r.mp4")
        service.update(job_r.id, __import__("app.schemas.job", fromlist=["JobUpdate"]).JobUpdate(
            status=JobStatus.DOWNLOADING
        ))
        service.update(job_r.id, __import__("app.schemas.job", fromlist=["JobUpdate"]).JobUpdate(
            status=JobStatus.TRANSCRIBING
        ))
        service.update(job_r.id, __import__("app.schemas.job", fromlist=["JobUpdate"]).JobUpdate(
            status=JobStatus.ANALYZING
        ))
        service.update(job_r.id, __import__("app.schemas.job", fromlist=["JobUpdate"]).JobUpdate(
            status=JobStatus.RENDERING
        ))

        requeued = service.recover_pipeline_jobs()
        assert job_t.id in requeued
        assert job_r.id in requeued

        recovered_t = service.get(job_t.id)
        assert recovered_t.status == JobStatus.TRANSCRIBING.value
        assert "recovery" in recovered_t.payload

        recovered_r = service.get(job_r.id)
        assert recovered_r.status == JobStatus.RENDERING.value
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Storage download endpoint — path traversal
# ---------------------------------------------------------------------------


def _client(settings: Settings) -> TestClient:
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


def test_download_serves_stored_file(settings: Settings) -> None:
    """A saved artifact is downloadable via the storage endpoint."""
    from app.providers.factory import build_storage

    storage = build_storage(settings)
    ref = storage.save("clips/test-job/clip_0.mp4", b"\x00\x00\x00\x1cftyp")
    assert ref == "clips/test-job/clip_0.mp4"

    with TestClient(create_app(settings)) as client:
        resp = client.get(
            f"/api/v1/storage/{ref}",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        )
        assert resp.status_code == 200
        assert resp.content.startswith(b"\x00\x00\x00\x1cftyp")


def test_download_rejects_path_traversal(settings: Settings) -> None:
    """Traversal attempts must be rejected with 400, never escape storage root."""
    with TestClient(create_app(settings)) as client:
        # Use %2e%2e so the path reaches the route intact (client collapses literal ..).
        resp = client.get(
            "/api/v1/storage/%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        )
        assert resp.status_code == 400
        body = resp.json()
        msg = body.get("error", {}).get("message", "") or body.get("detail", "")
        assert "invalid" in msg.lower()


def test_download_404_for_missing_file(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        resp = client.get(
            "/api/v1/storage/clips/nonexistent/clip.mp4",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        )
        assert resp.status_code == 404
