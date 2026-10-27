"""Hardening tests: pipeline attempts cap, silence honesty, --once exit."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from app.core.config import Settings
from app.db.session import create_engine_from_url, create_session_factory, init_db
from app.models.job import JobStatus
from app.providers.transcription import FasterWhisperProvider, TranscriptionError
from app.schemas.job import JobUpdate
from app.services.jobs import JobService
from app.storage.local import LocalStorage
from app.workers.pipeline import PipelineWorker

SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "worker.py"


class StubComponent:
    """Counts calls; optionally raises."""

    def __init__(self, outcome=None) -> None:
        self._outcome = outcome
        self.calls = 0

    def _act(self) -> None:
        self.calls += 1
        if isinstance(self._outcome, Exception):
            raise self._outcome


class StubTranscriber(StubComponent):
    def transcribe(self, source_ref, *, progress=None) -> dict:
        self._act()
        return {"language": "en", "duration_seconds": 5.0, "segments": []}


def _service(settings: Settings) -> JobService:
    engine = create_engine_from_url(settings.ce_database_url)
    init_db(engine)
    return JobService(create_session_factory(engine))


def _job_in_transcribing(service: JobService, storage: LocalStorage):
    job = service.create(source_url="https://example.com/v.mp4")
    service.claim_next_queued()
    asset_ref = f"sources/{job.id}/source.mp4"
    storage.save(asset_ref, b"bytes")
    service.complete_acquisition(job.id, {"asset_ref": asset_ref})
    return service.get(job.id)


def test_pipeline_attempts_cap_fails_honestly(settings: Settings, tmp_path: Path) -> None:
    service = _service(settings)
    storage = LocalStorage(tmp_path / "store")
    job = _job_in_transcribing(service, storage)
    # Simulate repeated crash/recover cycles: cap is 3, already at 3.
    service.update(job.id, JobUpdate(payload={"pipeline_attempts": 3}))

    transcriber = StubTranscriber()
    worker = PipelineWorker(
        job_service=service,
        transcriber=transcriber,
        clip_detector=StubComponent(),
        captioner=StubComponent(),
        renderer=StubComponent(),
        settings=settings,
    )
    outcome = worker.run_once()

    assert outcome.action == "failed"
    assert "pipeline attempts exhausted" in (outcome.detail or "")
    assert transcriber.calls == 0  # never invoked once exhausted
    failed = service.get(job.id)
    assert failed.status == JobStatus.FAILED.value
    assert "attempts exhausted" in failed.error_message


def test_vad_silence_maps_to_clear_error(settings: Settings, tmp_path: Path) -> None:
    """All-audio-filtered silence must say 'no speech', not leak internals."""
    storage = LocalStorage(tmp_path / "store")
    ref = storage.save("sources/j/source.mp4", b"bytes")

    provider = FasterWhisperProvider(storage=storage, model_size="tiny")

    class FakeModel:
        def transcribe(self, path, **kwargs):
            raise ValueError("max() iterable argument is empty")

    provider._model = FakeModel()
    try:
        provider.transcribe(ref)
        raise AssertionError("expected TranscriptionError")
    except TranscriptionError as exc:
        assert "no speech detected" in str(exc)
        assert "iterable argument is empty" not in str(exc)


def _cli(args: list[str], env_extra: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **env_extra},
        timeout=180,
    )


def test_cli_once_exits_on_empty_queue(settings: Settings, tmp_path: Path) -> None:
    """--once must exit immediately on an empty queue, not poll forever."""
    env = {"CE_DATABASE_URL": settings.ce_database_url}
    assert _cli(["run", "--once"], env).returncode == 0
    assert _cli(["pipeline", "run", "--once"], env).returncode == 0
