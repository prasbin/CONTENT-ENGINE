"""Application error types and FastAPI exception handlers.

Every error response uses a stable JSON shape:
    {"error": {"code": "...", "message": "...", "details": ...?}}
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("content_engine.errors")


class ContentEngineError(Exception):
    """Base class for all domain errors raised by CONTENT ENGINE."""

    code = "internal_error"
    status_code = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(ContentEngineError):
    code = "not_found"
    status_code = 404


class AuthenticationError(ContentEngineError):
    code = "unauthorized"
    status_code = 401


class AuthorizationError(ContentEngineError):
    code = "forbidden"
    status_code = 403


class InvalidTransitionError(ContentEngineError):
    code = "invalid_status_transition"
    status_code = 409


class InvalidSourceUrlError(ContentEngineError):
    code = "invalid_source_url"
    status_code = 422


class StoragePathError(ContentEngineError):
    code = "invalid_storage_path"
    status_code = 400


class ProviderNotConfiguredError(ContentEngineError):
    code = "provider_not_configured"
    status_code = 501


def _error_body(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


def _http_code(status_code: int) -> str:
    return {
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
    }.get(status_code, "http_error")


def register_exception_handlers(app: FastAPI) -> None:
    """Attach consistent JSON error handlers to the app."""

    @app.exception_handler(ContentEngineError)
    async def _domain_error(request: Request, exc: ContentEngineError) -> Any:
        from starlette.responses import JSONResponse

        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder(_error_body(exc.code, exc.message)),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> Any:
        from starlette.responses import JSONResponse

        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(
                _error_body("validation_error", "Request validation failed", exc.errors())
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> Any:
        from starlette.responses import JSONResponse

        message = str(exc.detail) if exc.detail else "Request failed"
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder(_error_body(_http_code(exc.status_code), message)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> Any:
        from starlette.responses import JSONResponse

        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=_error_body("internal_error", "Internal server error"),
        )
