"""Database initialization, job persistence, and transition tests."""

from __future__ import annotations

import pytest
from app.core.config import Settings
from app.core.errors import InvalidTransitionError, NotFoundError
from app.db.session import (
    create_engine_from_url,
    create_session_factory,
    init_db,
    normalize_database_url,
)
from app.models.job import (
    PIPELINE_ORDER,
    Job,
    JobStatus,
    can_transition,
    utc_iso,
)
from app.schemas.job import JobUpdate
from app.services.jobs import JobService
from sqlalchemy import inspect as sa_inspect


def _service(settings: Settings) -> tuple[JobService, object]:
    engine = create_engine_from_url(settings.ce_database_url)
    init_db(engine)
    return JobService(create_session_factory(engine)), engine


def test_init_db_creates_jobs_table(settings: Settings) -> None:
    engine = create_engine_from_url(settings.ce_database_url)
    try:
        init_db(engine)
        tables = sa_inspect(engine).get_table_names()
        assert "jobs" in tables
        columns = {column["name"] for column in sa_inspect(engine).get_columns("jobs")}
        assert {
            "id",
            "source_url",
            "status",
            "progress",
            "error_message",
            "payload",
            "created_at",
            "updated_at",
        } <= columns
    finally:
        engine.dispose()


def test_job_created_with_defaults(settings: Settings) -> None:
    service, engine = _service(settings)
    try:
        job = service.create(source_url="https://example.com/video.mp4")
        assert job.id
        assert job.status == JobStatus.QUEUED.value
        assert job.progress == 0
        assert job.error_message is None
        assert job.payload == {}
        assert job.created_at is not None
        assert job.updated_at is not None
    finally:
        engine.dispose()


def test_job_persists_across_engine_restart(settings: Settings) -> None:
    service, engine = _service(settings)
    job = service.create(
        source_url="https://example.com/persist.mp4",
        payload={"niche": "gym"},
    )
    engine.dispose()  # simulates API/server restart

    service2, engine2 = _service(settings)
    try:
        loaded = service2.get(job.id)
        assert loaded.source_url == "https://example.com/persist.mp4"
        assert loaded.payload == {"niche": "gym"}
        assert loaded.status == JobStatus.QUEUED.value
    finally:
        engine2.dispose()


def test_status_and_progress_update_persists(settings: Settings) -> None:
    service, engine = _service(settings)
    try:
        job = service.create(source_url="https://example.com/a.mp4")
        updated = service.update(
            job.id,
            JobUpdate(status=JobStatus.DOWNLOADING, progress=25),
        )
        assert updated.status == JobStatus.DOWNLOADING.value
        assert updated.progress == 25
        assert utc_iso(updated.updated_at) >= utc_iso(updated.created_at)

        reloaded = service.get(job.id)
        assert reloaded.status == "downloading"
        assert reloaded.progress == 25
    finally:
        engine.dispose()


def test_invalid_transition_is_rejected_and_not_persisted(settings: Settings) -> None:
    service, engine = _service(settings)
    try:
        job = service.create(source_url="https://example.com/a.mp4")
        with pytest.raises(InvalidTransitionError):
            service.update(job.id, JobUpdate(status=JobStatus.PUBLISHED))
        assert service.get(job.id).status == JobStatus.QUEUED.value
    finally:
        engine.dispose()


def test_failed_job_can_only_be_retried(settings: Settings) -> None:
    service, engine = _service(settings)
    try:
        job = service.create(source_url="https://example.com/a.mp4")
        service.update(job.id, JobUpdate(status=JobStatus.FAILED, error_message="boom"))

        with pytest.raises(InvalidTransitionError):
            service.update(job.id, JobUpdate(status=JobStatus.DOWNLOADING))

        retried = service.update(job.id, JobUpdate(status=JobStatus.QUEUED, error_message=None))
        assert retried.status == JobStatus.QUEUED.value
        assert retried.error_message is None
    finally:
        engine.dispose()


def test_list_with_pagination_and_status_filter(settings: Settings) -> None:
    service, engine = _service(settings)
    try:
        for index in range(3):
            service.create(source_url=f"https://example.com/{index}.mp4")

        jobs, total = service.list(limit=2, offset=0)
        assert total == 3
        assert len(jobs) == 2

        queued, queued_total = service.list(status=JobStatus.QUEUED)
        assert queued_total == 3
        assert len(queued) == 3

        failed, failed_total = service.list(status=JobStatus.FAILED)
        assert failed_total == 0
        assert failed == []
    finally:
        engine.dispose()


def test_get_missing_job_raises_not_found(settings: Settings) -> None:
    service, engine = _service(settings)
    try:
        with pytest.raises(NotFoundError):
            service.get("does-not-exist")
    finally:
        engine.dispose()


def test_can_transition_covers_every_status() -> None:
    all_statuses = set(JobStatus)
    assert set(PIPELINE_ORDER) | {JobStatus.FAILED} == all_statuses
    assert can_transition(JobStatus.QUEUED, JobStatus.QUEUED) is True
    assert can_transition(JobStatus.QUEUED, JobStatus.FAILED) is True
    assert can_transition(JobStatus.QUEUED, JobStatus.PUBLISHED) is False
    assert can_transition(JobStatus.FAILED, JobStatus.QUEUED) is True
    assert can_transition(JobStatus.FAILED, JobStatus.DOWNLOADING) is False
    assert can_transition(JobStatus.REVIEW, JobStatus.RENDERING) is True
    assert can_transition(JobStatus.PUBLISHED, JobStatus.REVIEW) is False
    assert can_transition(JobStatus.PUBLISHED, JobStatus.PUBLISHED) is True


def test_database_urls_reject_empty() -> None:
    with pytest.raises(ValueError):
        create_engine_from_url("")


def test_jobs_table_named_correctly() -> None:
    assert Job.__tablename__ == "jobs"


def test_normalize_database_url_anchors_relative_sqlite_paths(tmp_path, monkeypatch) -> None:
    from app.core import paths as paths_module

    monkeypatch.setattr(paths_module, "PROJECT_ROOT", tmp_path)

    normalized = normalize_database_url("sqlite:///./data/x.db")
    assert normalized == "sqlite:///" + (tmp_path / "data" / "x.db").as_posix()

    # untouched cases
    assert normalize_database_url("sqlite:///:memory:") == "sqlite:///:memory:"
    assert normalize_database_url("sqlite:////abs/y.db") == "sqlite:////abs/y.db"
    absolute = "sqlite:///" + (tmp_path / "z.db").as_posix()
    assert normalize_database_url(absolute) == absolute
    assert normalize_database_url("postgresql://user:pw@host/db") == "postgresql://user:pw@host/db"


def test_relative_sqlite_engine_created_under_project_root(tmp_path, monkeypatch) -> None:
    from app.core import paths as paths_module

    monkeypatch.setattr(paths_module, "PROJECT_ROOT", tmp_path)
    engine = create_engine_from_url("sqlite:///./rel_test.db")
    try:
        init_db(engine)
        assert engine.url.database == (tmp_path / "rel_test.db").as_posix()
        assert (tmp_path / "rel_test.db").is_file()
        assert "jobs" in sa_inspect(engine).get_table_names()
    finally:
        engine.dispose()
