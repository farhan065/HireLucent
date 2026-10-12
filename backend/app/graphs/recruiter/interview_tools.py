"""The Recruiter Agent's interview tools.

GetShortlistedCandidates is read-only. The other three send emails and
calendar invitations, so they always wait for the interviewer's approval.
Before the interviewer is asked, a preparer turns the model's dates and
times into exact times, checks every rule and builds an email preview, so
the schedule card shows exactly what will be sent.

The model only ever sees candidate IDs, names, scores and times. Email
addresses stay in the database and go only to the Google MCP server.
"""

import json
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, ConflictError
from app.db.session import SessionLocal
from app.models import Candidate, InterviewSession, Job, ScreeningResult
from app.models.enums import CandidateStatus, SessionStatus
from app.services import interview_emails, scheduling_service, session_service
from app.services.interview_times import app_zone, describe, parse_local
from app.services.scheduling_service import Slot

SCHEDULED_PREFIX = "Interviews scheduled: "
MOVED_PREFIX = "Interview moved: "
CANCELLED_PREFIX = "Interview cancelled: "
NO_JOB = "This conversation has no saved job yet, so there is no one to interview."

DATE = Field(pattern=r"^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD")
TIME = Field(pattern=r"^\d{2}:\d{2}$", description="24-hour HH:MM")
LENGTH = Field(ge=15, le=120, description="Length in minutes")


class GetShortlistedCandidates(BaseModel):
    """List this job's shortlisted candidates with their candidate_id, name,
    final score, rank and any interview already scheduled. Use it before
    scheduling, and never guess a candidate_id."""


class InterviewSlot(BaseModel):
    candidate_id: int
    date: str = DATE
    start_time: str = TIME
    duration_minutes: int = LENGTH


class ScheduleInterviews(BaseModel):
    """Schedule video interviews for shortlisted candidates. Times are in
    the interviewer's time zone. The interviewer approves the schedule, then
    each candidate is sent an email and a calendar invitation."""

    interviews: list[InterviewSlot] = Field(min_length=1, max_length=20)


class RescheduleInterview(InterviewSlot):
    """Move one candidate's interview that has not started to a new time.
    The candidate is sent the new time and a new link."""


class CancelInterview(BaseModel):
    """Cancel one candidate's interview that has not started. The candidate
    is told by email and through the calendar."""

    candidate_id: int


def _job_id(state: dict[str, Any]) -> int:
    job_id = state.get("saved_job_id")
    if not job_id:
        raise ConflictError(NO_JOB)
    return job_id


def _times(slot: dict[str, Any]) -> tuple[datetime, datetime]:
    try:
        start = parse_local(slot["date"], slot["start_time"])
    except ValueError as exc:
        raise ConflictError(
            f"{slot['date']} {slot['start_time']} is not a valid date and time."
        ) from exc
    return start, start + timedelta(minutes=slot["duration_minutes"])


def _candidate_in_job(db: Session, job_id: int, candidate_id: int) -> Candidate:
    candidate = db.get(Candidate, candidate_id)
    if candidate is None or candidate.job_id != job_id:
        raise ConflictError(f"Candidate {candidate_id} is not part of this job.")
    return candidate


def _row(name: str, slot: dict[str, Any], start: datetime, end: datetime) -> dict[str, Any]:
    return {
        "candidate_id": slot["candidate_id"],
        "candidate_name": name,
        "date": slot["date"],
        "start_time": slot["start_time"],
        "duration_minutes": slot["duration_minutes"],
        "start": start.isoformat(),
        "end": end.isoformat(),
        "when": describe(start, end),
    }


def _preview(email: interview_emails.Email) -> dict[str, str]:
    return {"subject": email.subject, "text": email.text}


def check_batch(rows: list[dict[str, Any]]) -> None:
    """Refuse the same candidate twice, or two interviews at the same time."""
    ids = [row["candidate_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ConflictError("A candidate appears twice. Schedule each candidate once.")
    ordered = sorted(rows, key=lambda row: row["start"])
    for earlier, later in zip(ordered, ordered[1:]):
        if later["start"] < earlier["end"]:
            raise ConflictError(
                f"The interviews of {earlier['candidate_name']} and "
                f"{later['candidate_name']} overlap. Give them different times."
            )


# --- GetShortlistedCandidates ---


def shortlisted_rows(db: Session, job_id: int) -> list[dict[str, Any]]:
    """The candidates the interviewer can schedule, best first."""
    candidates = db.scalars(
        select(Candidate)
        .join(ScreeningResult, isouter=True)
        .where(
            Candidate.job_id == job_id,
            Candidate.status.in_(
                (CandidateStatus.SHORTLISTED, CandidateStatus.INTERVIEW_SCHEDULED)
            ),
        )
        .order_by(ScreeningResult.final_rank)
    )
    rows = []
    for candidate in candidates:
        upcoming = session_service.find_scheduled(db, job_id, candidate.id)
        result = candidate.screening_result
        rows.append(
            {
                "candidate_id": candidate.id,
                "name": candidate.full_name,
                "final_score": result.final_score if result else None,
                "rank": result.final_rank if result else None,
                "interview": (
                    describe(upcoming.scheduled_start, upcoming.scheduled_end)
                    if upcoming
                    else None
                ),
            }
        )
    return rows


def get_shortlisted(arguments: dict[str, Any], state: dict[str, Any]) -> tuple[str, dict]:
    with SessionLocal() as db:
        rows = shortlisted_rows(db, _job_id(state))
    if not rows:
        return "No candidates are shortlisted for this job yet.", {}
    return json.dumps(rows), {}


# --- ScheduleInterviews ---


def prepare_schedule(arguments: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    job_id = _job_id(state)
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        rows = []
        for slot in arguments["interviews"]:
            candidate = _candidate_in_job(db, job_id, slot["candidate_id"])
            start, end = _times(slot)
            try:
                session_service.check_new(db, candidate.id, start, end, state["user_id"])
            except AppError as exc:
                raise ConflictError(f"{candidate.full_name}: {exc.message}") from exc
            rows.append(_row(candidate.full_name, slot, start, end))
        check_batch(rows)
        first = rows[0]
        example = interview_emails.invitation(
            first["candidate_name"],
            job.title,
            datetime.fromisoformat(first["start"]),
            datetime.fromisoformat(first["end"]),
            interview_emails.PREVIEW_LINK,
        )
        return {
            "job_title": job.title,
            "time_zone": app_zone().key,
            "interviews": rows,
            "email_preview": _preview(example),
        }


def schedule_interviews(arguments: dict[str, Any], state: dict[str, Any]) -> tuple[str, dict]:
    slots = [
        Slot(
            row["candidate_id"],
            datetime.fromisoformat(row["start"]),
            datetime.fromisoformat(row["end"]),
        )
        for row in arguments["interviews"]
    ]
    with SessionLocal() as db:
        outcomes = scheduling_service.schedule(db, _job_id(state), slots, state["user_id"])
    results = [
        {
            "candidate_id": outcome.candidate_id,
            "candidate_name": outcome.candidate_name,
            "status": outcome.status,
            "when": (
                describe(outcome.scheduled_start, outcome.scheduled_end)
                if outcome.scheduled_start
                else None
            ),
            "warning": outcome.warning,
            "error": outcome.error,
        }
        for outcome in outcomes
    ]
    return SCHEDULED_PREFIX + json.dumps(results), {}


# --- RescheduleInterview ---


def _scheduled_session(db: Session, job_id: int, candidate: Candidate) -> InterviewSession:
    session = session_service.find_scheduled(db, job_id, candidate.id)
    if session is None:
        raise ConflictError(f"{candidate.full_name} has no upcoming interview to change.")
    return session


def prepare_reschedule(arguments: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    job_id = _job_id(state)
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        candidate = _candidate_in_job(db, job_id, arguments["candidate_id"])
        session = _scheduled_session(db, job_id, candidate)
        start, end = _times(arguments)
        session_service.check_move(db, session, start, end)
        example = interview_emails.rescheduled(
            candidate.full_name, job.title, start, end, interview_emails.PREVIEW_LINK
        )
        return {
            **_row(candidate.full_name, arguments, start, end),
            "session_id": session.id,
            "job_title": job.title,
            "previous_when": describe(session.scheduled_start, session.scheduled_end),
            "email_preview": _preview(example),
        }


def reschedule_interview(arguments: dict[str, Any], state: dict[str, Any]) -> tuple[str, dict]:
    with SessionLocal() as db:
        change = scheduling_service.reschedule(
            db,
            arguments["session_id"],
            datetime.fromisoformat(arguments["start"]),
            datetime.fromisoformat(arguments["end"]),
        )
    result = {
        "candidate_name": arguments["candidate_name"],
        "when": arguments["when"],
        "warning": change.warning,
    }
    return MOVED_PREFIX + json.dumps(result), {}


# --- CancelInterview ---


def prepare_cancel(arguments: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    job_id = _job_id(state)
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        candidate = _candidate_in_job(db, job_id, arguments["candidate_id"])
        session = _scheduled_session(db, job_id, candidate)
        if session.status != SessionStatus.SCHEDULED:
            raise ConflictError("Only an interview that has not started can be cancelled.")
        example = interview_emails.cancelled(
            candidate.full_name, job.title, session.scheduled_start, session.scheduled_end
        )
        return {
            "candidate_id": candidate.id,
            "candidate_name": candidate.full_name,
            "session_id": session.id,
            "job_title": job.title,
            "when": describe(session.scheduled_start, session.scheduled_end),
            "email_preview": _preview(example),
        }


def cancel_interview(arguments: dict[str, Any], state: dict[str, Any]) -> tuple[str, dict]:
    with SessionLocal() as db:
        change = scheduling_service.cancel(db, arguments["session_id"])
    result = {
        "candidate_name": arguments["candidate_name"],
        "when": arguments["when"],
        "warning": change.warning,
    }
    return CANCELLED_PREFIX + json.dumps(result), {}
