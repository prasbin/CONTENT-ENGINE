"""Job endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_job_service, require_auth
from app.models.job import Job, JobStatus
from app.schemas.job import JobCreate, JobList, JobRead, JobUpdate
from app.services.jobs import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])

AuthDep = Annotated[None, Depends(require_auth)]
ServiceDep = Annotated[JobService, Depends(get_job_service)]


@router.post(
    "",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a job from a video URL",
)
def create_job(body: JobCreate, service: ServiceDep, _: AuthDep) -> Job:
    return service.create(source_url=body.source_url, payload=body.payload)


@router.get("", response_model=JobList, summary="List jobs")
def list_jobs(
    service: ServiceDep,
    _: AuthDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    job_status: Annotated[JobStatus | None, Query(alias="status")] = None,
) -> JobList:
    jobs, total = service.list(limit=limit, offset=offset, status=job_status)
    return JobList(items=[JobRead.model_validate(job) for job in jobs], total=total)


@router.get("/{job_id}", response_model=JobRead, summary="Get a job")
def get_job(job_id: str, service: ServiceDep, _: AuthDep) -> Job:
    return service.get(job_id)


@router.patch("/{job_id}", response_model=JobRead, summary="Update a job")
def update_job(
    job_id: str,
    body: JobUpdate,
    service: ServiceDep,
    _: AuthDep,
) -> Job:
    return service.update(job_id, body)
