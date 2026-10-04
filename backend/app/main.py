"""HireLucent backend application entry point."""

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings

API_DESCRIPTION = (
    "Backend API for HireLucent, an AI-powered recruitment and interview "
    "intelligence platform. AI assists and people decide: every score is "
    "traceable to CV or transcript evidence."
)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=API_DESCRIPTION,
    )
    app.include_router(api_router)
    return app


app = create_app()