"""Top-level API router that collects all route modules."""

from fastapi import APIRouter

from app.api.routes import (
    ai,
    auth,
    chat,
    chat_ws,
    graphs,
    health,
    jobs,
    knowledge,
    tasks,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(ai.router)
api_router.include_router(graphs.router)
api_router.include_router(tasks.router)
api_router.include_router(jobs.router)
api_router.include_router(chat.router)
api_router.include_router(chat_ws.router)
api_router.include_router(knowledge.router)
