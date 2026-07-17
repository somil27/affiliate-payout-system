"""Global exception handlers mapping DomainError → HTTP responses."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.exceptions import DomainError
from app.schemas.common import ErrorResponse

logger = logging.getLogger(__name__)


def _envelope(request: Request, *, code: str, message: str, status: int) -> JSONResponse:
    body = ErrorResponse(
        code=code,
        message=message,
        request_id=getattr(request.state, "request_id", None),
    )
    return JSONResponse(status_code=status, content=body.model_dump())


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(request: Request, exc: DomainError):  # type: ignore[unused-ignore]
        return _envelope(request, code=exc.code, message=exc.message, status=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        return _envelope(
            request,
            code="validation_error",
            message=exc.errors()[0]["msg"] if exc.errors() else "Invalid request",
            status=422,
        )

    @app.exception_handler(IntegrityError)
    async def _integrity(request: Request, exc: IntegrityError):
        logger.warning("db.integrity_error", extra={"error": str(exc.orig)})
        return _envelope(
            request,
            code="conflict",
            message="Database constraint violated",
            status=409,
        )

    @app.exception_handler(SQLAlchemyError)
    async def _sql(request: Request, exc: SQLAlchemyError):
        logger.exception("db.unhandled")
        return _envelope(
            request,
            code="database_error",
            message="A database error occurred",
            status=500,
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logger.exception("http.unhandled_exception")
        return _envelope(
            request,
            code="internal_error",
            message="An unexpected error occurred",
            status=500,
        )
