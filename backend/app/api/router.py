"""Top-level API router that collects all route modules."""

from fastapi import APIRouter

from app.api.routes import (
    ai,
    assessments,
    auth,
    candidates,
    chat,
    chat_ws,
    feedback,
    graphs,
    health,
    intake,
    interviews,
    join,
    jobs,
    knowledge,
    screening,
    tasks,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(ai.router)
api_router.include_router(graphs.router)
api_router.include_router(tasks.router)
api_router.include_router(jobs.router)
api_router.include_router(intake.router)
api_router.include_router(candidates.router)
api_router.include_router(screening.router)
api_router.include_router(interviews.router)
api_router.include_router(interviews.session_router)
api_router.include_router(assessments.job_router)
api_router.include_router(assessments.session_router)
api_router.include_router(feedback.job_router)
api_router.include_router(feedback.candidate_router)
api_router.include_router(join.router)
api_router.include_router(chat.router)
api_router.include_router(chat_ws.router)
api_router.include_router(knowledge.router)
