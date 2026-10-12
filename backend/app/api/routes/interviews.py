"""Interview endpoints for a job."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_interviewer
from app.db.session import get_db
from app.models import InterviewSession
from app.schemas.error import ErrorResponse
from app.schemas.interview import InterviewSessionSummary
from app.services import session_service

router = APIRouter(
    prefix="/jobs/{job_id}", tags=["Interviews"], dependencies=[Depends(require_interviewer)]
)


@router.get(
    "/interviews",
    response_model=list[InterviewSessionSummary],
    summary="List a job's interviews",
    responses={404: {"model": ErrorResponse, "description": "Job not found"}},
)
def list_interviews(job_id: int, db: Session = Depends(get_db)) -> list[InterviewSession]:
    """Every interview of the job, earliest first, cancelled ones included.
    Times are in UTC; the browser shows them in local time."""
    return session_service.list_for_job(db, job_id)
