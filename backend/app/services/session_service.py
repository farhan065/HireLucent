"""SessionService: interview sessions and their private join links.

A session is one interview between the interviewer and one shortlisted
candidate, linked to the candidate's job. Only the SHA-256 hash of the join
token is stored. The token itself is returned once, when the session is
created or moved, so it can be put in the invitation email.

Calendar events and invitation emails are added by the scheduling step;
this service only keeps the records and their rules.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.errors import AppError, ConflictError, NotFoundError
from app.core.logging import get_logger, log_event
from app.models import Candidate, InterviewSession, Job
from app.models.enums import CandidateStatus, SessionStatus

logger = get_logger(__name__)

TOKEN_BYTES = 32
MIN_NOTICE = timedelta(minutes=15)
MIN_LENGTH = timedelta(minutes=15)
MAX_LENGTH = timedelta(minutes=120)
MAX_AHEAD = timedelta(days=60)

# Sessions that still hold a time slot.
ACTIVE = (SessionStatus.SCHEDULED, SessionStatus.IN_PROGRESS)
# A candidate can be scheduled once shortlisted, and again after an
# earlier interview has finished.
SCHEDULABLE = (CandidateStatus.SHORTLISTED, CandidateStatus.INTERVIEW_SCHEDULED)

RULES_LOCKED = (
    "The requirements and weights cannot change while this job has interviews. "
    "Every interviewed candidate must be scored with the same rules."
)


class JoinState(StrEnum):
    """What the candidate's link allows right now."""

    TOO_EARLY = "too_early"
    OPEN = "open"
    MISSED = "missed"
    ENDED = "ended"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def hash_token(token: str) -> str:
    """The value stored for a join token. The token is never stored."""
    return hashlib.sha256(token.encode()).hexdigest()


def new_join_token() -> tuple[str, str]:
    """A new random join token and its hash."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    return token, hash_token(token)


def check_times(start: datetime, end: datetime, now: datetime) -> None:
    """Refuse times an interview cannot have."""
    if start.tzinfo is None or end.tzinfo is None:
        raise AppError("Interview times must include their time zone.")
    if start < now + MIN_NOTICE:
        raise AppError("An interview must start at least 15 minutes from now.")
    if start > now + MAX_AHEAD:
        raise AppError("An interview can be scheduled at most 60 days ahead.")
    if not MIN_LENGTH <= end - start <= MAX_LENGTH:
        raise AppError("An interview must last between 15 and 120 minutes.")


def join_state(session: InterviewSession, now: datetime) -> JoinState:
    """Whether the candidate can join now.

    The link opens a few minutes before the start. A running interview can
    be joined (or rejoined after a dropped connection) until it ends, even
    after its scheduled end.
    """
    if session.status in (SessionStatus.COMPLETED, SessionStatus.CANCELLED):
        return JoinState.ENDED
    if session.status == SessionStatus.IN_PROGRESS:
        return JoinState.OPEN
    opens_at = session.scheduled_start - timedelta(
        minutes=get_settings().join_opens_minutes_before
    )
    if now < opens_at:
        return JoinState.TOO_EARLY
    if now <= session.scheduled_end:
        return JoinState.OPEN
    return JoinState.MISSED


def create_session(
    db: Session,
    candidate_id: int,
    start: datetime,
    end: datetime,
    created_by: int,
    now: datetime | None = None,
) -> tuple[InterviewSession, str]:
    """Schedule an interview and return it with its join token.

    The token is returned only here. Keep it only as long as it takes to put
    it in the invitation.
    """
    check_times(start, end, now or now_utc())
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise NotFoundError("This candidate does not exist.")
    if candidate.status not in SCHEDULABLE:
        raise ConflictError("Only shortlisted candidates can be scheduled for an interview.")
    if _active_count(db, InterviewSession.candidate_id == candidate_id):
        raise ConflictError("This candidate already has an upcoming interview.")
    _ensure_free(db, created_by, start, end)

    token, token_hash = new_join_token()
    session = InterviewSession(
        candidate_id=candidate_id,
        job_id=candidate.job_id,
        created_by=created_by,
        scheduled_start=start,
        scheduled_end=end,
        join_token_hash=token_hash,
        status=SessionStatus.SCHEDULED,
    )
    db.add(session)
    candidate.status = CandidateStatus.INTERVIEW_SCHEDULED
    db.commit()
    log_event(
        logger,
        "interview_scheduled",
        session_id=session.id,
        candidate_id=candidate_id,
        job_id=candidate.job_id,
    )
    return session, token


def reschedule(
    db: Session,
    session_id: int,
    start: datetime,
    end: datetime,
    now: datetime | None = None,
) -> tuple[InterviewSession, str]:
    """Move an interview that has not started. It gets a new join token, so
    the old link stops working."""
    session = get_session(db, session_id)
    if session.status != SessionStatus.SCHEDULED:
        raise ConflictError("Only an interview that has not started can be moved.")
    check_times(start, end, now or now_utc())
    _ensure_free(db, session.created_by, start, end, exclude_id=session.id)

    token, token_hash = new_join_token()
    session.scheduled_start = start
    session.scheduled_end = end
    session.join_token_hash = token_hash
    session.candidate_joined_at = None
    db.commit()
    log_event(logger, "interview_rescheduled", session_id=session.id)
    return session, token


def cancel(db: Session, session_id: int, now: datetime | None = None) -> InterviewSession:
    """Cancel an interview that has not started. Its link stops working.

    The candidate goes back to the shortlist unless they have had an
    interview already, so they can be scheduled again.
    """
    session = get_session(db, session_id)
    if session.status != SessionStatus.SCHEDULED:
        raise ConflictError("Only an interview that has not started can be cancelled.")
    session.status = SessionStatus.CANCELLED
    session.cancelled_at = now or now_utc()
    had_interview = db.scalar(
        select(func.count())
        .select_from(InterviewSession)
        .where(
            InterviewSession.candidate_id == session.candidate_id,
            InterviewSession.id != session.id,
            InterviewSession.status != SessionStatus.CANCELLED,
        )
    )
    if not had_interview:
        session.candidate.status = CandidateStatus.SHORTLISTED
    db.commit()
    log_event(logger, "interview_cancelled", session_id=session.id)
    return session


def get_session(db: Session, session_id: int) -> InterviewSession:
    session = db.get(InterviewSession, session_id)
    if session is None:
        raise NotFoundError("This interview does not exist.")
    return session


def list_for_job(db: Session, job_id: int) -> list[InterviewSession]:
    """The job's interviews, earliest first, with each candidate's name."""
    if db.get(Job, job_id) is None:
        raise NotFoundError("This job does not exist.")
    return list(
        db.scalars(
            select(InterviewSession)
            .options(joinedload(InterviewSession.candidate))
            .where(InterviewSession.job_id == job_id)
            .order_by(InterviewSession.scheduled_start)
        )
    )


def find_by_token(db: Session, token: str) -> InterviewSession | None:
    """The interview a join token belongs to, or None."""
    return db.scalar(
        select(InterviewSession).where(InterviewSession.join_token_hash == hash_token(token))
    )


def ensure_rules_can_change(db: Session, job_id: int) -> None:
    """Refuse to change a job's requirements or weights once it has any
    interview that is not cancelled."""
    count = db.scalar(
        select(func.count())
        .select_from(InterviewSession)
        .where(
            InterviewSession.job_id == job_id,
            InterviewSession.status != SessionStatus.CANCELLED,
        )
    )
    if count:
        raise ConflictError(RULES_LOCKED)


def _active_count(db: Session, *conditions) -> int:
    return db.scalar(
        select(func.count())
        .select_from(InterviewSession)
        .where(InterviewSession.status.in_(ACTIVE), *conditions)
    )


def _ensure_free(
    db: Session,
    interviewer_id: int | None,
    start: datetime,
    end: datetime,
    exclude_id: int | None = None,
) -> None:
    """Refuse a time that overlaps another interview of the same
    interviewer, for any job."""
    conditions = [
        InterviewSession.created_by == interviewer_id,
        InterviewSession.scheduled_start < end,
        InterviewSession.scheduled_end > start,
    ]
    if exclude_id is not None:
        conditions.append(InterviewSession.id != exclude_id)
    if _active_count(db, *conditions):
        raise ConflictError("You already have an interview at that time.")
