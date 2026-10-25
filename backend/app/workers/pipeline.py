"""Pipeline worker: transcription -> clip detection -> rendering -> review.

Claims jobs that have completed acquisition (status 'transcribing') and
runs the full downstream pipeline. Each stage uses a legal state
transition; failures are recorded honestly with the job marked 'failed'.

This worker is intentionally separate from AcquisitionWorker so the two
can run independently (acquisition is I/O-bound; transcription/rendering
are CPU-bound).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.core.errors import ContentEngineError
from app.models.job import Job, JobStatus
from app.providers.base import ProgressCallback
from app.providers.captions import TranscriptCaptionProvider
from app.providers.clip_detection import HeuristicClipDetector
from app.providers.renderer import FFmpegRenderer
from app.providers.transcription import FasterWhisperProvider
from app.services.jobs import JobService

logger = logging.getLogger("content_engine.worker.pipeline")


@dataclass(frozen=True)
class PipelineOutcome:
    action: str  # "processed" | "failed" | "idle"
    job_id: str | None
    detail: str | None = None


class PipelineWorker:
    """Runs transcription through rendering for acquired jobs."""

    def __init__(
        self,
        *,
        job_service: JobService,
        transcriber: FasterWhisperProvider,
        clip_detector: HeuristicClipDetector,
        captioner: TranscriptCaptionProvider,
        renderer: FFmpegRenderer,
        settings: Settings,
    ) -> None:
        self._jobs = job_service
        self._transcriber = transcriber
        self._clip_detector = clip_detector
        self._captioner = captioner
        self._renderer = renderer
        self._settings = settings

    def recover_interrupted(self) -> list[str]:
        requeued = self._jobs.recover_pipeline_jobs()
        if requeued:
            logger.warning("recovered %d interrupted pipeline job(s): %s", len(requeued), requeued)
        return requeued

    def run_once(self) -> PipelineOutcome:
        job = self._claim_pipeline_job()
        if job is None:
            return PipelineOutcome("idle", None)

        try:
            if job.status == JobStatus.TRANSCRIBING.value:
                return self._run_from_transcription(job)
            if job.status == JobStatus.RENDERING.value:
                return self._run_from_rendering(job)
        except ContentEngineError as exc:
            self._jobs.mark_failed(job.id, f"{exc.code}: {exc.message}")
            logger.error("pipeline job %s failed [%s]: %s", job.id, exc.code, exc.message)
            return PipelineOutcome("failed", job.id, f"{exc.code}: {exc.message}")
        except Exception as exc:
            self._jobs.mark_failed(job.id, f"unexpected pipeline error: {exc}")
            logger.exception("pipeline job %s failed unexpectedly", job.id)
            return PipelineOutcome("failed", job.id, str(exc))

        self._jobs.mark_failed(job.id, f"job in unexpected state for pipeline: {job.status}")
        return PipelineOutcome("failed", job.id)

    def _claim_pipeline_job(self) -> Job | None:
        """Return the oldest job in a pipeline-ready state (transcribing/rendering).

        Jobs are claimed without a state change — they stay in their current
        stage while the worker runs it, so a crash leaves them recoverable.
        """
        for target in (JobStatus.TRANSCRIBING, JobStatus.RENDERING):
            job = self._jobs._claim_in_status(target)  # noqa: SLF001 — same-package helper
            if job is not None:
                return job
        return None

    def _run_from_transcription(self, job: Job) -> PipelineOutcome:
        asset_ref = self._require_asset_ref(job)

        def on_progress(val: int) -> None:
            self._jobs.set_progress(job.id, val)

        progress: ProgressCallback = on_progress
        transcript = self._transcriber.transcribe(asset_ref, progress=progress)
        self._jobs.complete_transcription(job.id, transcript)

        clips = self._clip_detector.detect_moments(transcript)
        self._jobs.complete_clip_detection(job.id, clips)
        return self._render_clips(job.id, transcript, clips)

    def _run_from_rendering(self, job: Job) -> PipelineOutcome:
        payload = job.payload or {}
        transcript = payload.get("transcript") or {}
        clips = payload.get("clips") or []
        if not transcript or not clips:
            raise ContentEngineError("cannot re-render: missing transcript or clips in payload")
        return self._render_clips(job.id, transcript, clips)

    def _render_clips(self, job_id: str, transcript: dict, clips: list[dict]) -> PipelineOutcome:
        asset_ref = self._require_asset_ref_from_payload(job_id, transcript)
        public_base = self._settings.ce_public_base_url
        if public_base:
            public_base = public_base.rstrip("/")

        completed: list[dict[str, Any]] = []
        for clip in clips:
            target = int(clip["target_duration"])
            start = float(clip["start"])
            end = float(clip["end"])
            cues = self._captioner.cues_for_clip(transcript, start, end)
            output_ref = f"clips/{job_id}/clip_{clip['index']}_{target}s.mp4"

            stored_ref = self._renderer.render_vertical(
                asset_ref, start, end, output_ref, captions=cues, progress=None
            )
            download_url = (
                f"{public_base}/api/v1/storage/{stored_ref}" if public_base
                else f"/api/v1/storage/{stored_ref}"
            )
            completed.append({**clip, "asset_ref": stored_ref, "download_url": download_url})

        self._jobs.complete_rendering(job_id, completed)
        logger.info("pipeline job %s complete: %d clip(s) rendered", job_id, len(completed))
        return PipelineOutcome("processed", job_id)

    @staticmethod
    def _require_asset_ref(job: Job) -> str:
        acq = (job.payload or {}).get("acquisition") or {}
        ref = acq.get("asset_ref")
        if not ref:
            raise ContentEngineError("job has no acquired source asset to transcribe")
        return ref

    def _require_asset_ref_from_payload(self, job_id: str, transcript: dict) -> str:
        job = self._jobs.get(job_id)
        return self._require_asset_ref(job)

    def run(self, *, max_jobs: int | None = None, poll_seconds: float = 2.0) -> None:
        self.recover_interrupted()
        processed = 0
        try:
            while max_jobs is None or processed < max_jobs:
                outcome = self.run_once()
                if outcome.action == "idle":
                    time.sleep(poll_seconds)
                    continue
                processed += 1
        except KeyboardInterrupt:
            logger.info("pipeline worker stopped by keyboard interrupt")
