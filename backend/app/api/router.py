"""Top-level API router that collects all route modules."""

from fastapi import APIRouter

from app.api.routes import ai, auth, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(ai.router)