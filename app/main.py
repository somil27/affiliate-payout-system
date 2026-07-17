"""FastAPI application factory."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.database import init_db
from app.middleware.error_handlers import register_exception_handlers
from app.middleware.request_context import RequestContextMiddleware

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        init_db()
        logger.info("app.started", extra={"env": settings.app_env, "version": __version__})
        yield
        logger.info("app.stopped")

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Backend service for affiliate-sale advance payouts, reconciliation, "
            "and withdrawal management. See `/docs` for the OpenAPI UI."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    app.include_router(api_router)

    return app
