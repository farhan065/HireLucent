"""JoinService: the candidate's side of the private interview link.

The candidate has no account. Their link holds a secret token; only its
hash is stored. Opening the link shows the interview's state. Joining, with
consent, puts the candidate in the waiting room and gives the browser a
short-lived pass for this one interview. The pass carries a fingerprint of
the link, so it stops working when the interview moves to a new link, and
it is refused once the interview has ended or was cancelled.

While waiting, the candidate's page checks in every few seconds, so the
interviewer sees who is really waiting.

Interviews scheduled with F7 also have a PIN, asked for before joining, and
an identity photo, taken after joining and before the waiting room
(identity_service). Neither ever blocks a candidate who has the PIN.
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError, UnauthorizedError
from app.core.logging import get_logger, log_event
from app.core.security import create_access_token
from app.models import InterviewSession, Job
from app.models.enums import SessionStatus, UserRole
from app.services import identity_service, pin_service, room_service, session_service
from app.services.session_service import JoinState, hash_token, now_utc

logger = get_logger(__name__)

LINK_NOT_FOUND = "This interview link no longer works."
NOT_OPEN_YET = "The interview cannot be joined yet. Please come back when Join opens."
WRONG_PIN = "That PIN is not right. Check your calendar invitation and try again."
PIN_LOCKED = "Too many wrong tries. The link is locked for a few minutes."
# The pass lasts until a while after the interview's end, in case it runs over.
PASS_EXTRA = timedelta(hours=2)
FINGERPRINT_LENGTH = 16


def _fingerprint(session: InterviewSession) -> str:
    return session.join_token_hash[:FINGERPRINT_LENGTH]


def _find(db: Session, token: str) -> InterviewSession:
    session = db.scalar(
        select(InterviewSession).where(InterviewSession.join_token_hash == hash_token(token))
    )
    if session is None:
        raise NotFoundError(LINK_NOT_FOUND)
    return session


def _state(session: InterviewSession, now: datetime) -> str:
    """too_early, open or ended. A missed interview counts as ended."""
    state = session_service.join_state(session, now)
    if state in (JoinState.MISSED, JoinState.ENDED):
        return "ended"
    return state.value


def link_info(db: Session, token: str, now: datetime | None = None) -> dict[str, Any]:
    """What the candidate's page shows: the job, the time and whether Join is
    open. Only the first name is given; never an email address."""
    session = _find(db, token)
    job = db.get(Job, session.job_id)
    opens = get_settings().join_opens_minutes_before
    name = session.candidate.full_name.split()
    return {
        "state": _state(session, now or now_utc()),
        "first_name": name[0] if name else "",
        "job_title": job.title,
        "scheduled_start": session.scheduled_start,
        "scheduled_end": session.scheduled_end,
        "opens_at": session.scheduled_start - timedelta(minutes=opens),
        "length_minutes": int(
            (session.scheduled_end - session.scheduled_start).total_seconds() // 60
        ),
        "pin_required": session.pin_hash is not None,
    }


def check_pin(
    db: Session, token: str, pin: str, now: datetime | None = None
) -> pin_service.PinCheck:
    """Check the PIN the candidate typed. Wrong tries are counted; the
    fifth locks the link for a while."""
    now = now or now_utc()
    session = _find(db, token)
    if _state(session, now) == "ended":
        raise NotFoundError(LINK_NOT_FOUND)
    if session.pin_hash is None:
        return pin_service.PinCheck(pin_service.OK)
    result = pin_service.check(session, pin, now)
    db.commit()
    return result


def enter(
    db: Session, token: str, now: datetime | None = None, pin: str | None = None
) -> str:
    """Put the candidate in the waiting room after they agreed to the
    transcript (and the identity photo) and, for an interview with a PIN,
    typed the right PIN. Returns their pass for this interview."""
    now = now or now_utc()
    session = _find(db, token)
    state = _state(session, now)
    if state == "ended":
        raise NotFoundError(LINK_NOT_FOUND)
    if state == "too_early":
        raise ConflictError(NOT_OPEN_YET)
    if session.pin_hash is not None:
        result = pin_service.check(session, pin or "", now)
        if result.result != pin_service.OK:
            db.commit()
            if result.result == pin_service.LOCKED:
                raise ConflictError(PIN_LOCKED)
            raise UnauthorizedError(WRONG_PIN)
    if session.consent_given_at is None:
        session.consent_given_at = now
    # Before the start the candidate waits to be let in. Once the interview
    # has started, they go straight back into the room.
    if session.status == SessionStatus.SCHEDULED:
        if not session.candidate_waiting:
            session.candidate_joined_at = now
        session.candidate_seen_at = now
    db.commit()
    log_event(logger, "candidate_entered_waiting_room", session_id=session.id)
    valid_until = max(session.scheduled_end, now) + PASS_EXTRA
    return create_access_token(
        subject=str(session.candidate_id),
        role=UserRole.CANDIDATE,
        expires_in=valid_until - now,
        session_id=session.id,
        link=_fingerprint(session),
    )


def _session_for(db: Session, session_id: int | None, link: str | None) -> InterviewSession:
    """The interview the candidate's pass is for, if the pass still fits it."""
    session = db.get(InterviewSession, session_id or 0)
    if session is None or link != _fingerprint(session):
        raise UnauthorizedError(LINK_NOT_FOUND)
    return session


def check_in(
    db: Session, session_id: int | None, link: str | None, now: datetime | None = None
) -> str:
    """The waiting page checking in, with the pass's session and link
    fingerprint. Returns waiting, started or ended."""
    now = now or now_utc()
    session = _session_for(db, session_id, link)
    if _state(session, now) == "ended":
        return "ended"
    if session.status == SessionStatus.IN_PROGRESS:
        return "started"
    session.candidate_seen_at = now
    db.commit()
    return "waiting"


def leave(db: Session, session_id: int | None, link: str | None) -> None:
    """The candidate left the waiting room."""
    session = _session_for(db, session_id, link)
    session.candidate_seen_at = None
    db.commit()


def room_pass(db: Session, session_id: int | None, link: str | None) -> dict:
    """The candidate's pass for the video room, once they were admitted."""
    return room_service.candidate_pass(db, _session_for(db, session_id, link))


def needs_photo(db: Session, token: str) -> bool:
    """Whether the candidate still has to take the identity photo."""
    return identity_service.needs_photo(_find(db, token))


def identity_photo(
    db: Session,
    session_id: int | None,
    link: str | None,
    content: bytes,
    now: datetime | None = None,
) -> tuple[str, int | None]:
    """Check the photo taken when joining (done, or retry with tries left)."""
    now = now or now_utc()
    session = _session_for(db, session_id, link)
    if _state(session, now) == "ended":
        raise NotFoundError(LINK_NOT_FOUND)
    return identity_service.check_photo(db, session, content, now)


def skip_identity(
    db: Session, session_id: int | None, link: str | None, reason: str, now: datetime | None = None
) -> None:
    """The candidate joins without the photo (no camera, or gave up)."""
    now = now or now_utc()
    session = _session_for(db, session_id, link)
    if _state(session, now) == "ended":
        raise NotFoundError(LINK_NOT_FOUND)
    identity_service.skip(db, session, reason, now)
