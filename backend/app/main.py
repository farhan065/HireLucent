"""HireLucent backend application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.graphs.checkpointer import close_checkpointer, setup_checkpointer
from app.schemas.error import ErrorResponse
from app.services.task_service import fail_interrupted_tasks

API_DESCRIPTION = (
    "Backend API for HireLucent, an AI-powered recruitment and interview "
    "intelligence platform. AI assists and people decide: every score is "
    "traceable to CV or transcript evidence."
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Prepare shared resources at startup and release them at shutdown."""
    setup_checkpointer()
    fail_interrupted_tasks()
    yield
    close_checkpointer()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=API_DESCRIPTION,
        lifespan=lifespan,
        responses={
            422: {"model": ErrorResponse, "description": "Validation error"},
            500: {"model": ErrorResponse, "description": "Internal error"},
        },
    )
    register_exception_handlers(app)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(api_router)
    return app


app = create_app()