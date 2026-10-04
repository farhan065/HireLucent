"""HireLucent backend application entry point."""

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.schemas.error import ErrorResponse

API_DESCRIPTION = (
    "Backend API for HireLucent, an AI-powered recruitment and interview "
    "intelligence platform. AI assists and people decide: every score is "
    "traceable to CV or transcript evidence."
)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=API_DESCRIPTION,
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