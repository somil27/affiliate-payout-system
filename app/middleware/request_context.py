"""Request-ID middleware for log correlation."""
from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("http")

_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request-id + basic access log entry to every request."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        request_id = request.headers.get(_HEADER) or uuid.uuid4().hex
        request.state.request_id = request_id
        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception:
            logger.exception(
                "http.unhandled",
                extra={"request_id": request_id, "path": request.url.path, "method": request.method},
            )
            raise
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers[_HEADER] = request_id
        logger.info(
            "http.request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )
        return response
