"""Acquisition worker: claims queued jobs, runs video acquisition, handles retries/recovery."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from app.core.config import Settings
from app.core.errors import ContentEngineError
from app.providers.base import VideoSourceProvider
from app.services.jobs import JobService

logger = logging.getLogger("content_engine.worker.acquisition")


@dataclass(frozen=True)
class WorkerOutcome:
    action: str  # "processed" | "failed" | "idle"
    job_id: str | None
    detail: str | None = None


class AcquisitionWorker:
    """Consumes queued acquisition jobs from the database queue."""

    def __init__(
        self,
        *,
        job_service: JobService,
        provider: VideoSourceProvider,
        settings: Settings,
    ) -> None:
        self._job_service = job_service
        self._provider = provider
        self._settings = settings

    def recover_interrupted(self) -> list[str]:
        """Requeue any jobs stuck in 'downloading' from a previous crash."""
        requeued = self._job_service.recover_downloading_jobs()
        if requeued:
            logger.warning(
                "recovered %d interrupted downloading job(s): %s",
                len(requeued),
                requeued,
            )
        return requeued

    def run_once(self) -> WorkerOutcome:
        job = self._job_service.claim_next_queued()
        if job is None:
            return WorkerOutcome("idle", None)

        payload = job.payload or {}
        attempts = int(payload.get("attempts", 1))
        max_attempts = self._settings.ce_max_acquisition_attempts

        logger.info(
            "processing job %s (attempt %d/%d) url=%s",
            job.id,
            attempts,
            max_attempts,
            job.source_url,
        )

        if attempts > max_attempts:
            msg = f"acquisition attempts exhausted ({attempts} > max {max_attempts})"
            self._job_service.mark_failed(job.id, msg)
            logger.error("job %s failed: %s", job.id, msg)
            return WorkerOutcome("failed", job.id, msg)

        def on_progress(val: int) -> None:
            self._job_service.set_progress(job.id, val)

        try:
            result = self._provider.acquire(
                job.source_url,
                job_id=job.id,
                progress=on_progress,
            )
        except ContentEngineError as exc:
            msg = f"{exc.code}: {exc.message}"
            self._job_service.mark_failed(job.id, msg)
            logger.error("job %s failed with domain error [%s]: %s", job.id, exc.code, exc.message)
            return WorkerOutcome("failed", job.id, msg)
        except Exception as exc:
            msg = f"unexpected acquisition error: {exc}"
            self._job_service.mark_failed(job.id, msg)
            logger.exception("job %s failed with unexpected exception", job.id)
            return WorkerOutcome("failed", job.id, msg)

        self._job_service.complete_acquisition(job.id, result.to_payload())
        logger.info(
            "job %s acquisition completed successfully (asset=%s)",
            job.id,
            result.asset_ref,
        )
        return WorkerOutcome("processed", job.id)

    def run(
        self,
        *,
        max_jobs: int | None = None,
        poll_seconds: float = 2.0,
        stop_when_idle: bool = False,
    ) -> None:
        """Run continuously or for up to ``max_jobs`` items.

        With ``stop_when_idle``, an empty queue ends the loop instead of
        polling (used by the ``--once`` CLI mode).
        """
        self.recover_interrupted()
        processed = 0
        try:
            while max_jobs is None or processed < max_jobs:
                outcome = self.run_once()
                if outcome.action == "idle":
                    if stop_when_idle:
                        break
                    time.sleep(poll_seconds)
                    continue
                processed += 1
        except KeyboardInterrupt:
            logger.info("acquisition worker stopped by keyboard interrupt")
