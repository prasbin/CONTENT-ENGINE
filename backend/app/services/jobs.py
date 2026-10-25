"""Service layer for jobs: the only write path to the jobs table."""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import InvalidTransitionError, NotFoundError
from app.db.session import session_scope
from app.models.job import Job, JobStatus, can_transition, utcnow
from app.schemas.job import JobUpdate


class JobService:
    """CRUD + status transitions for persistent jobs."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create(self, *, source_url: str, payload: dict | None = None) -> Job:
        with session_scope(self._session_factory) as session:
            job = Job(source_url=source_url, payload=dict(payload or {}))
            session.add(job)
            session.flush()
            session.expunge(job)
            return job

    def get(self, job_id: str) -> Job:
        with session_scope(self._session_factory) as session:
            job = session.get(Job, job_id)
            if job is None:
                raise NotFoundError(f"job '{job_id}' not found")
            session.expunge(job)
            return job

    def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: JobStatus | None = None,
    ) -> tuple[list[Job], int]:
        with session_scope(self._session_factory) as session:
            filters = [Job.status == status.value] if status is not None else []
            total = session.scalar(select(func.count()).select_from(Job).where(*filters)) or 0
            jobs = list(
                session.scalars(
                    select(Job)
                    .where(*filters)
                    .order_by(Job.created_at.desc(), Job.id)
                    .limit(limit)
                    .offset(offset)
                )
            )
            for job in jobs:
                session.expunge(job)
            return jobs, total

    def update(self, job_id: str, changes: JobUpdate) -> Job:
        with session_scope(self._session_factory) as session:
            job = session.get(Job, job_id)
            if job is None:
                raise NotFoundError(f"job '{job_id}' not found")

            changed_fields = changes.model_fields_set

            if "status" in changed_fields and changes.status is not None:
                new_status = changes.status.value
                if new_status != job.status and not can_transition(job.status, new_status):
                    raise InvalidTransitionError(
                        f"cannot move job '{job_id}' from '{job.status}' to '{new_status}'"
                    )
                job.status = new_status

            if "progress" in changed_fields and changes.progress is not None:
                job.progress = max(0, min(100, int(changes.progress)))

            if "error_message" in changed_fields:
                job.error_message = changes.error_message

            if changes.payload:
                job.payload = {**(job.payload or {}), **changes.payload}

            job.updated_at = utcnow()
            session.add(job)
            session.flush()
            session.expunge(job)
            return job

    def claim_next_queued(self) -> Job | None:
        """Atomically claim the oldest queued job (CAS on status='queued')."""
        return self._claim_in_status(JobStatus.QUEUED, start_status=JobStatus.DOWNLOADING)

    def _claim_in_status(
        self, status: JobStatus, *, start_status: JobStatus | None = None
    ) -> Job | None:
        """Atomically claim the oldest job in ``status``.

        When ``start_status`` is given the job moves to it (acquisition: queued -> downloading).
        When it is None the job keeps its current status (pipeline stages are
        claimed in place so a crash leaves them recoverable in the same stage).
        """
        target = (start_status or status).value
        for _ in range(3):
            with session_scope(self._session_factory) as session:
                job_id = session.scalar(
                    select(Job.id)
                    .where(Job.status == status.value)
                    .order_by(Job.created_at.asc(), Job.id.asc())
                    .limit(1)
                )
                if job_id is None:
                    return None
                job = session.get(Job, job_id)
                if job is None or job.status != status.value:
                    continue
                payload = dict(job.payload or {})
                attempts = int(payload.get("attempts", 0)) + 1
                payload["attempts"] = attempts

                res = session.execute(
                    update(Job)
                    .where(Job.id == job_id, Job.status == status.value)
                    .values(
                        status=target,
                        progress=10,
                        payload=payload,
                        updated_at=utcnow(),
                    )
                )
                if res.rowcount != 1:
                    continue
                session.flush()
                refreshed = session.get(Job, job_id)
                session.expunge(refreshed)
                return refreshed
        return None

    def set_progress(self, job_id: str, progress: int) -> None:
        with session_scope(self._session_factory) as session:
            job = session.get(Job, job_id)
            if job is not None:
                job.progress = max(0, min(100, int(progress)))
                job.updated_at = utcnow()
                session.add(job)

    def mark_failed(self, job_id: str, error_message: str) -> None:
        with session_scope(self._session_factory) as session:
            job = session.get(Job, job_id)
            if job is not None and can_transition(job.status, JobStatus.FAILED.value):
                job.status = JobStatus.FAILED.value
                job.error_message = error_message[:4000]
                job.updated_at = utcnow()
                session.add(job)

    def complete_acquisition(self, job_id: str, acquisition_payload: dict) -> None:
        with session_scope(self._session_factory) as session:
            job = session.get(Job, job_id)
            if job is not None and can_transition(job.status, JobStatus.TRANSCRIBING.value):
                job.status = JobStatus.TRANSCRIBING.value
                job.progress = 100
                job.payload = {**(job.payload or {}), "acquisition": acquisition_payload}
                job.updated_at = utcnow()
                session.add(job)

    def _advance(
        self,
        session: Session,
        job: Job,
        target: JobStatus,
        *,
        payload: dict | None = None,
        progress: int | None = None,
    ) -> None:
        target_val = target.value
        if not can_transition(job.status, target_val):
            raise InvalidTransitionError(
                f"cannot move job '{job.id}' from '{job.status}' to '{target_val}'"
            )
        job.status = target_val
        if progress is not None:
            job.progress = max(0, min(100, int(progress)))
        if payload:
            job.payload = {**(job.payload or {}), **payload}
        job.updated_at = utcnow()
        session.add(job)

    def complete_transcription(self, job_id: str, transcript: dict) -> None:
        with session_scope(self._session_factory) as session:
            job = session.get(Job, job_id)
            if job is not None:
                self._advance(
                    session, job, JobStatus.ANALYZING,
                    payload={"transcript": transcript}, progress=40,
                )

    def complete_clip_detection(self, job_id: str, clips: list[dict]) -> None:
        with session_scope(self._session_factory) as session:
            job = session.get(Job, job_id)
            if job is not None:
                self._advance(
                    session, job, JobStatus.RENDERING,
                    payload={"clips": clips}, progress=50,
                )

    def complete_rendering(self, job_id: str, clips_with_refs: list[dict]) -> None:
        """Move rendering -> review, storing clip asset refs + download URLs."""
        with session_scope(self._session_factory) as session:
            job = session.get(Job, job_id)
            if job is not None:
                self._advance(
                    session, job, JobStatus.REVIEW,
                    payload={"clips": clips_with_refs}, progress=100,
                )

    def recover_pipeline_jobs(self) -> list[str]:
        """Requeue jobs stuck mid-pipeline back to a safe re-runnable stage.

        transcribing/analyzing -> transcribing (re-transcribe, idempotent overwrite).
        rendering/captioning   -> rendering   (re-render from stored transcript).
        """
        requeued: list[str] = []
        with session_scope(self._session_factory) as session:
            for status, target in (
                (JobStatus.TRANSCRIBING, JobStatus.TRANSCRIBING),
                (JobStatus.ANALYZING, JobStatus.TRANSCRIBING),
                (JobStatus.RENDERING, JobStatus.RENDERING),
                (JobStatus.CAPTIONING, JobStatus.RENDERING),
            ):
                for job in session.scalars(select(Job).where(Job.status == status.value)):
                    if can_transition(job.status, target.value):
                        job.status = target.value
                        job.progress = 0
                        payload = dict(job.payload or {})
                        payload["recovery"] = {
                            "reason": f"interrupted while {job.status}",
                            "requeued_at": utcnow().isoformat(),
                        }
                        job.payload = payload
                        job.updated_at = utcnow()
                        session.add(job)
                        requeued.append(job.id)
            session.flush()
        return requeued

    def recover_downloading_jobs(self) -> list[str]:
        """Requeue jobs stuck in 'downloading' from a previous crash/restart."""
        requeued_ids: list[str] = []
        with session_scope(self._session_factory) as session:
            jobs = list(
                session.scalars(
                    select(Job).where(Job.status == JobStatus.DOWNLOADING.value)
                )
            )
            for job in jobs:
                if can_transition(job.status, JobStatus.QUEUED.value):
                    job.status = JobStatus.QUEUED.value
                    job.progress = 0
                    payload = dict(job.payload or {})
                    payload["recovery"] = {
                        "reason": "interrupted while downloading",
                        "requeued_at": utcnow().isoformat(),
                    }
                    job.payload = payload
                    job.updated_at = utcnow()
                    session.add(job)
                    requeued_ids.append(job.id)
            session.flush()
        return requeued_ids
