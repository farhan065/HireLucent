"""Interview endpoints: a job's interviews, and changes to one interview.

Scheduling, moving and cancelling send emails and calendar invitations, so
the screen asks the interviewer to confirm before calling them.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import Principal, require_interviewer
from app.db.session import get_db
from app.models import InterviewSession
from app.schemas.error import ErrorResponse
from app.schemas.interview import (
    InterviewChange,
    InterviewRules,
    InterviewSessionSummary,
    InterviewTime,
    ScheduleOutcome,
    ScheduleRequest,
)
from app.services import scheduling_service, session_service
from app.services.scheduling_service import Slot

router = APIRouter(
    prefix="/jobs/{job_id}", tags=["Interviews"], dependencies=[Depends(require_interviewer)]
)
session_router = APIRouter(
    prefix="/interviews", tags=["Interviews"], dependencies=[Depends(require_interviewer)]
)

JOB_NOT_FOUND = {404: {"model": ErrorResponse, "description": "Job not found"}}
SESSION_ERRORS = {
    404: {"model": ErrorResponse, "description": "Interview not found"},
    409: {"model": ErrorResponse, "description": "The interview has already started"},
    503: {"model": ErrorResponse, "description": "Google could not be reached"},
}


@router.get(
    "/interviews",
    response_model=list[InterviewSessionSummary],
    summary="List a job's interviews",
    responses=JOB_NOT_FOUND,
)
def list_interviews(job_id: int, db: Session = Depends(get_db)) -> list[InterviewSession]:
    """Every interview of the job, earliest first, cancelled ones included.
    Times are in UTC; the browser shows them in local time."""
    return session_service.list_for_job(db, job_id)


@router.post(
    "/interviews",
    response_model=list[ScheduleOutcome],
    summary="Schedule interviews and send the invitations",
    responses=JOB_NOT_FOUND,
)
def schedule_interviews(
    job_id: int,
    payload: ScheduleRequest,
    principal: Principal = Depends(require_interviewer),
    db: Session = Depends(get_db),
) -> list[ScheduleOutcome]:
    """Each candidate gets a calendar invitation and an email with a private
    join link. Returns one result per candidate; one failure does not stop
    the others."""
    slots = [Slot(item.candidate_id, item.start, item.end) for item in payload.interviews]
    return scheduling_service.schedule(db, job_id, slots, principal.subject_id)


@session_router.get(
    "/rules",
    response_model=InterviewRules,
    summary="Read the scheduling rules",
)
def read_rules() -> dict[str, int]:
    """How far ahead an interview must start, how early it can be joined,
    and its shortest and longest length, in minutes."""
    return session_service.rules()


@session_router.put(
    "/{session_id}",
    response_model=InterviewChange,
    summary="Move an interview to a new time",
    responses=SESSION_ERRORS,
)
def reschedule_interview(
    session_id: int, payload: InterviewTime, db: Session = Depends(get_db)
) -> InterviewChange:
    """The candidate gets the new time and a new link; the old link stops
    working."""
    return scheduling_service.reschedule(db, session_id, payload.start, payload.end)


@session_router.post(
    "/{session_id}/cancel",
    response_model=InterviewChange,
    summary="Cancel an interview",
    responses=SESSION_ERRORS,
)
def cancel_interview(session_id: int, db: Session = Depends(get_db)) -> InterviewChange:
    """The link stops working and the candidate is told by email and
    through the calendar."""
    return scheduling_service.cancel(db, session_id)


@session_router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a cancelled interview",
    responses={
        404: {"model": ErrorResponse, "description": "Interview not found"},
        409: {"model": ErrorResponse, "description": "The interview is not cancelled"},
    },
)
def delete_interview(session_id: int, db: Session = Depends(get_db)) -> None:
    """Removes a cancelled interview from the job's history. Nothing is sent
    to the candidate; Google was told when it was cancelled."""
    session_service.delete_cancelled(db, session_id)
