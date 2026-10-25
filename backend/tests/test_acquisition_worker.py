"""Tests for AcquisitionWorker, retries, recovery, and job status transitions."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.core.config import Settings
from app.core.errors import DownloadFailedError
from app.db.session import create_engine_from_url, create_session_factory, init_db
from app.models.job import JobStatus
from app.providers.base import AcquisitionResult
from app.services.jobs import JobService
from app.workers.acquisition import AcquisitionWorker


@pytest.fixture
def session_factory(tmp_path: Path):
    db_path = tmp_path / "test.db"
    engine = create_engine_from_url(f"sqlite:///{db_path}")
    init_db(engine)
    factory = create_session_factory(engine)
    yield factory
    engine.dispose()


class StubVideoProvider:
    def __init__(self, outcome: AcquisitionResult | Exception) -> None:
        self._outcome = outcome
        self.acquired_urls: list[str] = []

    def acquire(self, url: str, *, job_id: str, progress=None) -> AcquisitionResult:
        self.acquired_urls.append(url)
        if progress:
            progress(50)
            progress(100)
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


def test_worker_idle_when_no_queued_jobs(session_factory, tmp_path: Path) -> None:
    settings = Settings(_env_file=None)
    job_service = JobService(session_factory)
    provider = StubVideoProvider(
        AcquisitionResult(
            "sources/j/source.mp4",
            "https://youtube.com/watch?v=1",
            "source.mp4",
            "video/mp4",
            100,
        )
    )
    worker = AcquisitionWorker(
        job_service=job_service,
        provider=provider,
        settings=settings,
    )

    outcome = worker.run_once()
    assert outcome.action == "idle"
    assert outcome.job_id is None


def test_worker_processes_queued_job_successfully(session_factory, tmp_path: Path) -> None:
    settings = Settings(_env_file=None)
    job_service = JobService(session_factory)
    job = job_service.create(source_url="https://www.youtube.com/watch?v=abc123xyz")

    acq_res = AcquisitionResult(
        asset_ref=f"sources/{job.id}/source.mp4",
        source_url=job.source_url,
        filename="source.mp4",
        media_type="video/mp4",
        size_bytes=1024,
        duration_seconds=12.0,
        probed=True,
    )
    provider = StubVideoProvider(acq_res)
    worker = AcquisitionWorker(job_service=job_service, provider=provider, settings=settings)

    outcome = worker.run_once()
    assert outcome.action == "processed"
    assert outcome.job_id == job.id

    updated = job_service.get(job.id)
    assert updated.status == JobStatus.TRANSCRIBING.value
    assert updated.progress == 100
    assert updated.payload["acquisition"]["asset_ref"] == acq_res.asset_ref


def test_worker_handles_domain_error_and_fails_job(session_factory, tmp_path: Path) -> None:
    settings = Settings(_env_file=None)
    job_service = JobService(session_factory)
    job = job_service.create(source_url="https://youtube.com/watch?v=bad")

    provider = StubVideoProvider(DownloadFailedError("network timeout"))
    worker = AcquisitionWorker(job_service=job_service, provider=provider, settings=settings)

    outcome = worker.run_once()
    assert outcome.action == "failed"
    assert outcome.job_id == job.id

    failed_job = job_service.get(job.id)
    assert failed_job.status == JobStatus.FAILED.value
    assert "download_failed" in failed_job.error_message


def test_worker_recovers_interrupted_downloading_jobs(session_factory, tmp_path: Path) -> None:
    settings = Settings(_env_file=None)
    job_service = JobService(session_factory)
    job = job_service.create(source_url="https://youtube.com/watch?v=crash")

    # Force job into downloading state as if crashed mid-download
    job_service.claim_next_queued()
    stuck = job_service.get(job.id)
    assert stuck.status == JobStatus.DOWNLOADING.value

    provider = StubVideoProvider(
        AcquisitionResult("sources/j/source.mp4", "u", "f", "v/m", 10)
    )
    worker = AcquisitionWorker(job_service=job_service, provider=provider, settings=settings)

    requeued = worker.recover_interrupted()
    assert requeued == [job.id]

    recovered = job_service.get(job.id)
    assert recovered.status == JobStatus.QUEUED.value
    assert recovered.progress == 0
    assert "recovery" in recovered.payload
