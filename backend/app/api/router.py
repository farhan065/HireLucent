"""Top-level API router that collects all route modules."""

from fastapi import APIRouter

from app.api.routes import ai, auth, graphs, health, jobs, tasks

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(ai.router)
api_router.include_router(graphs.router)
api_router.include_router(tasks.router)
api_router.include_router(jobs.router)