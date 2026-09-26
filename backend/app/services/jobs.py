"""Service layer for jobs: the only write path to the jobs table."""

from __future__ import annotations

from sqlalchemy import func, select
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
                job.progress = changes.progress

            if "error_message" in changed_fields:
                job.error_message = changes.error_message

            if changes.payload:
                job.payload = {**(job.payload or {}), **changes.payload}

            job.updated_at = utcnow()
            session.add(job)
            session.flush()
            session.expunge(job)
            return job
