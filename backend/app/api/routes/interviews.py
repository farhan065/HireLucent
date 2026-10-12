"""Interview endpoints: a job's interviews, and changes to one interview.

Scheduling, moving and cancelling send emails and calendar invitations, so
the screen asks the interviewer to confirm before calling them.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import Principal, require_interviewer
from app.db.session import get_db
from app.models import InterviewSession, Job
from app.schemas.error import ErrorResponse
from app.schemas.interview import (
    InterviewChange,
    InterviewRoomInfo,
    InterviewRules,
    InterviewSessionSummary,
    InterviewTime,
    ScheduleOutcome,
    ScheduleRequest,
)
from app.schemas.video import RoomTokenResponse
from app.services import room_service, scheduling_service, session_service
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


@session_router.get(
    "/{session_id}",
    response_model=InterviewRoomInfo,
    summary="Read one interview for its room",
    responses={404: {"model": ErrorResponse, "description": "Interview not found"}},
)
def read_interview(session_id: int, db: Session = Depends(get_db)) -> InterviewRoomInfo:
    """The interview with its job, and whether the candidate is waiting.
    The room asks every few seconds."""
    session = session_service.get_session(db, session_id)
    job = db.get(Job, session.job_id)
    return InterviewRoomInfo(
        interview=InterviewSessionSummary.model_validate(session),
        job_id=job.id,
        job_title=job.title,
        job_code=job.job_code,
    )


ROOM_ERRORS = {
    404: {"model": ErrorResponse, "description": "Interview not found"},
    409: {"model": ErrorResponse, "description": "Not possible at this stage"},
}


@session_router.post(
    "/{session_id}/room",
    response_model=RoomTokenResponse,
    summary="Open the interview room",
    responses={**ROOM_ERRORS, 503: {"model": ErrorResponse, "description": "Video is not set up"}},
)
def open_room(session_id: int, db: Session = Depends(get_db)) -> dict:
    """The interviewer's pass for the video room, from when Join opens until
    the interview ends."""
    return room_service.open_room(db, session_id)


@session_router.post(
    "/{session_id}/admit",
    response_model=InterviewSessionSummary,
    summary="Let the waiting candidate in and start the interview",
    responses=ROOM_ERRORS,
)
def admit_candidate(session_id: int, db: Session = Depends(get_db)) -> InterviewSession:
    return room_service.admit(db, session_id)


@session_router.post(
    "/{session_id}/end",
    response_model=InterviewSessionSummary,
    summary="End the interview for both people",
    responses=ROOM_ERRORS,
)
def end_interview(session_id: int, db: Session = Depends(get_db)) -> InterviewSession:
    """Closes the video room; the candidate's link stops working."""
    return room_service.end(db, session_id)


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
