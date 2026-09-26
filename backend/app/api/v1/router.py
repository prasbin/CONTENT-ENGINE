"""API v1 router aggregation.

Versioning foundation: all v1 routes live under ``/api/v1``. Future
breaking changes go to ``/api/v2``; the unversioned ``/health`` stays
stable for load balancers.
"""

from fastapi import APIRouter

from app.api.v1 import health, jobs

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(jobs.router)
