"""SchedulingService: scheduling, moving and cancelling interviews.

The one place used by both the Interviews tab and the AI Agent, so both
behave the same. It is only ever called after the interviewer has approved
(the confirm dialog, or the schedule card in the conversation).

For each candidate:
    session (with a private link) -> calendar event -> email

The calendar invitation also holds the join link, so it is the step that
decides: if it cannot be created, the session is removed and nothing is
sent. If only the email fails, the interview stays scheduled with a
warning, because the candidate has the link in the calendar invitation.

Candidate email addresses go only to the Google MCP server. They are never
logged and never given to the AI.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, NotFoundError, ServiceUnavailableError
from app.core.logging import get_logger, log_event
from app.mcp_clients import client
from app.models import Candidate, InterviewSession, Job
from app.schemas.interview import InterviewChange, InterviewSessionSummary, ScheduleOutcome
from app.services import interview_emails, session_service
from app.services.interview_times import app_zone

logger = get_logger(__name__)

GOOGLE_TIMEOUT_SECONDS = 30
GOOGLE_FAILED = (
    "Google could not be reached. Check that the Google sign-in has not "
    "expired, then try again."
)
NOT_IN_JOB = "This candidate is not part of this job."
CALENDAR_FAILED = (
    "The calendar invitation could not be created, so nothing was sent. "
    "Try again in a moment."
)
EMAIL_FAILED = (
    "The email could not be sent. The candidate's calendar invitation has the "
    "join link."
)
MOVE_FAILED = (
    "The interview could not be moved because its calendar invitation could "
    "not be updated. Nothing was changed."
)


@dataclass(frozen=True)
class Slot:
    candidate_id: int
    start: datetime
    end: datetime


def join_link(token: str) -> str:
    return f"{get_settings().frontend_base_url.rstrip('/')}/interview/{token}"


def schedule(
    db: Session, job_id: int, slots: list[Slot], created_by: int
) -> list[ScheduleOutcome]:
    """Schedule each candidate in turn. One candidate's failure does not
    stop the others."""
    job = db.get(Job, job_id)
    if job is None:
        raise NotFoundError("This job does not exist.")
    return [_schedule_one(db, job, slot, created_by) for slot in slots]


def _schedule_one(db: Session, job: Job, slot: Slot, created_by: int) -> ScheduleOutcome:
    candidate = db.get(Candidate, slot.candidate_id)
    if candidate is None or candidate.job_id != job.id:
        return _failed(slot, "Unknown candidate", NOT_IN_JOB)
    try:
        session, token = session_service.create_session(
            db, candidate.id, slot.start, slot.end, created_by
        )
    except AppError as exc:
        return _failed(slot, candidate.full_name, exc.message)

    link = join_link(token)
    try:
        event = _google(
            "create_calendar_event",
            {
                "title": interview_emails.calendar_title(job.title),
                "description": interview_emails.calendar_description(job.title, link),
                "start": _local_iso(slot.start),
                "end": _local_iso(slot.end),
                "time_zone": app_zone().key,
                "attendee": candidate.email,
            },
        )
    except ServiceUnavailableError:
        session_service.discard(db, session)
        return _failed(slot, candidate.full_name, CALENDAR_FAILED)
    session.calendar_event_id = event.get("event_id")
    db.commit()

    email = interview_emails.invitation(
        candidate.full_name, job.title, slot.start, slot.end, link
    )
    warning = None if _send(candidate.email, email) else EMAIL_FAILED
    return ScheduleOutcome(
        candidate_id=candidate.id,
        candidate_name=candidate.full_name,
        status="scheduled",
        session_id=session.id,
        scheduled_start=session.scheduled_start,
        scheduled_end=session.scheduled_end,
        warning=warning,
    )


def reschedule(
    db: Session, session_id: int, start: datetime, end: datetime
) -> InterviewChange:
    """Move an interview. The calendar event is updated and the candidate is
    emailed the new time with a new link; the old link stops working."""
    session = session_service.get_session(db, session_id)
    before = (
        session.scheduled_start,
        session.scheduled_end,
        session.join_token_hash,
        session.candidate_joined_at,
    )
    session, token = session_service.reschedule(db, session_id, start, end)
    link = join_link(token)
    candidate, job = session.candidate, db.get(Job, session.job_id)

    if session.calendar_event_id:
        try:
            _google(
                "update_calendar_event",
                {
                    "event_id": session.calendar_event_id,
                    "start": _local_iso(start),
                    "end": _local_iso(end),
                    "time_zone": app_zone().key,
                    "description": interview_emails.calendar_description(job.title, link),
                },
            )
        except ServiceUnavailableError as exc:
            (
                session.scheduled_start,
                session.scheduled_end,
                session.join_token_hash,
                session.candidate_joined_at,
            ) = before
            db.commit()
            raise ServiceUnavailableError(MOVE_FAILED) from exc

    email = interview_emails.rescheduled(candidate.full_name, job.title, start, end, link)
    warning = None if _send(candidate.email, email) else EMAIL_FAILED
    return _change(session, warning)


def cancel(db: Session, session_id: int) -> InterviewChange:
    """Cancel an interview. Google tells the candidate through the calendar,
    and the candidate is also emailed. The cancellation stands even if
    Google cannot be reached; a warning says what could not be sent."""
    session = session_service.cancel(db, session_id)
    candidate, job = session.candidate, db.get(Job, session.job_id)
    problems = []
    if session.calendar_event_id:
        try:
            _google("cancel_calendar_event", {"event_id": session.calendar_event_id})
        except ServiceUnavailableError:
            problems.append("the calendar invitation could not be removed")
    email = interview_emails.cancelled(
        candidate.full_name, job.title, session.scheduled_start, session.scheduled_end
    )
    if not _send(candidate.email, email):
        problems.append("the cancellation email could not be sent")
    warning = None
    if problems:
        warning = "The interview is cancelled, but " + " and ".join(problems) + "."
    return _change(session, warning)


def _send(address: str, email: interview_emails.Email) -> bool:
    """Send one email. Returns False instead of raising, so a failed email
    never undoes an interview that is already in the calendar."""
    try:
        _google(
            "send_email",
            {"to": address, "subject": email.subject, "text": email.text, "html": email.html},
        )
    except ServiceUnavailableError:
        return False
    return True


def _google(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Call one tool of the Google MCP server and return its answer."""
    try:
        result = client.call_tool("google", tool, arguments, timeout=GOOGLE_TIMEOUT_SECONDS)
        if result.is_error:
            raise RuntimeError(f"{tool} reported an error")
    except Exception as exc:
        log_event(
            logger,
            "google_action_failed",
            level=logging.WARNING,
            tool=tool,
            error_type=type(exc).__name__,
        )
        raise ServiceUnavailableError(GOOGLE_FAILED) from exc
    if result.structured_content:
        return result.structured_content.get("result", result.structured_content)
    return json.loads(result.content[0].text) if result.content else {}


def _local_iso(moment: datetime) -> str:
    """A time with its offset in the app's time zone, for the calendar."""
    return moment.astimezone(app_zone()).isoformat()


def _failed(slot: Slot, name: str, reason: str) -> ScheduleOutcome:
    return ScheduleOutcome(
        candidate_id=slot.candidate_id, candidate_name=name, status="failed", error=reason
    )


def _change(session: InterviewSession, warning: str | None) -> InterviewChange:
    return InterviewChange(
        interview=InterviewSessionSummary.model_validate(session), warning=warning
    )
