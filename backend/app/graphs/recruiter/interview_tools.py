"""The Recruiter Agent's interview tools.

GetCandidates is read-only. The other three send, change or cancel calendar
invitations, so they always wait for the interviewer's approval. Before the
interviewer is asked, a preparer turns the model's dates and times into
exact times, checks every rule and builds a preview of the invitation, so
the card shows exactly what will be sent. The interviewer can change the
message paragraph on the card or by asking the agent.

The model only ever sees candidate IDs, names, scores, statuses and times.
Email addresses, phone numbers and links stay in the database; email
addresses go only to the Google MCP server.
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
from app.schemas.interview import EmailMessage
from app.services import interview_emails, scheduling_service, session_service
from app.services.interview_times import app_zone, describe, parse_local, zone_label
from app.services.scheduling_service import Slot

SCHEDULED_PREFIX = "Interviews scheduled: "
MOVED_PREFIX = "Interview moved: "
CANCELLED_PREFIX = "Interview cancelled: "
NO_JOB = "This conversation has no saved job yet, so there is no one to interview."

DATE = Field(pattern=r"^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD")
TIME = Field(pattern=r"^\d{2}:\d{2}$", description="24-hour HH:MM")
LENGTH = Field(ge=15, le=120, description="Length in minutes")
MESSAGE = Field(
    default=None,
    description=(
        "Only when the interviewer asks to change the message to the candidate: "
        "the message paragraph as plain text. The greeting, time, join link and "
        "signature are added by the app, so never include them."
    ),
)
MAX_LISTED = 50

# Candidates who have been ranked: screened and not excluded.
RANKED = (
    CandidateStatus.SCREENED,
    CandidateStatus.SHORTLISTED,
    CandidateStatus.SELECTED,
    CandidateStatus.INTERVIEW_SCHEDULED,
    CandidateStatus.ASSESSED,
)


class GetCandidates(BaseModel):
    """List this job's ranked candidates, best first (at most 50), with their
    candidate_id, name, final score, rank and interview status. Use it before
    scheduling or when asked about candidates, and never guess a
    candidate_id."""


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
    message: EmailMessage | None = MESSAGE


class RescheduleInterview(InterviewSlot):
    """Move one candidate's interview that has not started to a new time.
    The candidate is sent the new time and a new link."""

    message: EmailMessage | None = MESSAGE


class CancelInterview(BaseModel):
    """Cancel one candidate's interview that has not started. The candidate
    is told through the calendar."""

    candidate_id: int
    message: EmailMessage | None = MESSAGE


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


def _scores(candidate: Candidate) -> dict[str, Any]:
    """The final score and rank, shown beside the name on the card."""
    result = candidate.screening_result
    return {
        "final_score": result.final_score if result else None,
        "rank": result.final_rank if result else None,
    }


def _zone(moment: datetime) -> dict[str, str]:
    """The time zone of the card's times, for example "Dhaka, GMT+6"."""
    return {"time_zone": app_zone().key, "time_zone_label": zone_label(moment)}


def _email(
    kind: str, name: str, job_title: str, start: datetime, end: datetime, message: str | None
) -> dict[str, Any]:
    """The card's email preview, the interviewer's own message (None for
    the default) and the default message, which the card's editor offers."""
    preview = interview_emails.preview(kind, name, job_title, start, end, message)
    return {
        "message": message,
        "default_message": preview["default_message"],
        "email_preview": {"subject": preview["subject"], "text": preview["text"]},
    }


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


# --- GetCandidates ---


def interview_status(
    candidate: Candidate, sessions: list[InterviewSession], now: datetime
) -> tuple[str, str | None]:
    """The candidate's interview status and its time, from their interviews
    that were not cancelled. An interview still to come or under way counts
    before an earlier one that has finished."""
    if candidate.status == CandidateStatus.SCREENED:
        return "not_shortlisted", None
    for session in sessions:
        when = describe(session.scheduled_start, session.scheduled_end)
        if session.status == SessionStatus.IN_PROGRESS:
            return "interview_in_progress", when
        if session.status == SessionStatus.SCHEDULED:
            missed = session.scheduled_end < now
            return ("interview_missed" if missed else "interview_scheduled"), when
    finished = [s for s in sessions if s.status == SessionStatus.COMPLETED]
    if finished:
        last = max(finished, key=lambda s: s.scheduled_start)
        return "interviewed", describe(last.scheduled_start, last.scheduled_end)
    return "shortlisted_not_invited", None


def candidate_rows(db: Session, job_id: int) -> tuple[list[dict[str, Any]], int]:
    """The job's ranked candidates, best first, at most MAX_LISTED, and how
    many are ranked in all."""
    candidates = list(
        db.scalars(
            select(Candidate)
            .join(ScreeningResult, isouter=True)
            .where(Candidate.job_id == job_id, Candidate.status.in_(RANKED))
            .order_by(ScreeningResult.final_rank.asc().nulls_last(), Candidate.id)
        )
    )
    shown = candidates[:MAX_LISTED]
    sessions = db.scalars(
        select(InterviewSession).where(
            InterviewSession.job_id == job_id,
            InterviewSession.candidate_id.in_([c.id for c in shown]),
            InterviewSession.status != SessionStatus.CANCELLED,
        )
    )
    by_candidate: dict[int, list[InterviewSession]] = {}
    for session in sessions:
        by_candidate.setdefault(session.candidate_id, []).append(session)
    now = session_service.now_utc()
    rows = []
    for candidate in shown:
        status, when = interview_status(candidate, by_candidate.get(candidate.id, []), now)
        rows.append(
            {
                "candidate_id": candidate.id,
                "name": candidate.full_name,
                **_scores(candidate),
                "status": status,
                "interview": when,
            }
        )
    return rows, len(candidates)


def get_candidates(arguments: dict[str, Any], state: dict[str, Any]) -> tuple[str, dict]:
    with SessionLocal() as db:
        rows, total = candidate_rows(db, _job_id(state))
    if not rows:
        return "No candidates of this job have been screened and ranked yet.", {}
    return json.dumps({"ranked": total, "shown": len(rows), "candidates": rows}), {}


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
            rows.append({**_row(candidate.full_name, slot, start, end), **_scores(candidate)})
        check_batch(rows)
        first = rows[0]
        start = datetime.fromisoformat(first["start"])
        end = datetime.fromisoformat(first["end"])
        return {
            "job_title": job.title,
            **_zone(start),
            "interviews": rows,
            **_email(
                interview_emails.INVITATION,
                first["candidate_name"],
                job.title,
                start,
                end,
                arguments.get("message"),
            ),
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
        outcomes = scheduling_service.schedule(
            db, _job_id(state), slots, state["user_id"], arguments.get("message")
        )
    results = [
        {
            "candidate_id": outcome.candidate_id,
            "candidate_name": outcome.candidate_name,
            "status": outcome.status,
            "start": outcome.scheduled_start.isoformat() if outcome.scheduled_start else None,
            "end": outcome.scheduled_end.isoformat() if outcome.scheduled_end else None,
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
        return {
            **_row(candidate.full_name, arguments, start, end),
            **_zone(start),
            "session_id": session.id,
            "job_title": job.title,
            "previous_start": session.scheduled_start.isoformat(),
            "previous_end": session.scheduled_end.isoformat(),
            "previous_when": describe(session.scheduled_start, session.scheduled_end),
            **_email(
                interview_emails.MOVED,
                candidate.full_name,
                job.title,
                start,
                end,
                arguments.get("message"),
            ),
        }


def reschedule_interview(arguments: dict[str, Any], state: dict[str, Any]) -> tuple[str, dict]:
    with SessionLocal() as db:
        change = scheduling_service.reschedule(
            db,
            arguments["session_id"],
            datetime.fromisoformat(arguments["start"]),
            datetime.fromisoformat(arguments["end"]),
            arguments.get("message"),
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
        # Google's cancellation notice shows this text to the candidate.
        return {
            "candidate_id": candidate.id,
            "candidate_name": candidate.full_name,
            **_zone(session.scheduled_start),
            "session_id": session.id,
            "job_title": job.title,
            "start": session.scheduled_start.isoformat(),
            "end": session.scheduled_end.isoformat(),
            "when": describe(session.scheduled_start, session.scheduled_end),
            **_email(
                interview_emails.CANCELLED,
                candidate.full_name,
                job.title,
                session.scheduled_start,
                session.scheduled_end,
                arguments.get("message"),
            ),
        }


def cancel_interview(arguments: dict[str, Any], state: dict[str, Any]) -> tuple[str, dict]:
    with SessionLocal() as db:
        change = scheduling_service.cancel(db, arguments["session_id"], arguments.get("message"))
    result = {
        "candidate_name": arguments["candidate_name"],
        "when": arguments["when"],
        "warning": change.warning,
    }
    return CANCELLED_PREFIX + json.dumps(result), {}
