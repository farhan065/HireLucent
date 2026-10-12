"""RoomService: the live interview in its video room.

The interviewer opens the room when Join is open and waits there. The
candidate waits in the waiting room until the interviewer admits them;
admitting starts the interview. Only then does the candidate get a pass for
the video room, so nobody reaches the interviewer without being let in. A
candidate who drops out of a started interview can come straight back.

Only the interviewer ends the interview. Ending closes the video room, and
the candidate's link stops working.
"""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError
from app.core.logging import get_logger, log_event
from app.models import InterviewSession
from app.models.enums import SessionStatus
from app.services import session_service, video
from app.services.session_service import JoinState, now_utc

logger = get_logger(__name__)

INTERVIEWER = "interviewer"
CANDIDATE = "candidate"
# Room passes last until a while after the planned end, in case it runs over.
PASS_EXTRA = timedelta(hours=2)

NOT_OPEN_YET = "The room opens {minutes} minutes before the interview starts."
FINISHED = "This interview has ended or was cancelled."
NOT_WAITING = "The candidate is not in the waiting room."
NOT_STARTED = "The interview has not started."


def _room_pass(session: InterviewSession, identity: str, name: str, now: datetime) -> dict:
    room = video.room_name(session.id)
    valid_until = max(session.scheduled_end, now) + PASS_EXTRA
    return {
        "url": get_settings().livekit_url,
        "room": room,
        "identity": identity,
        "token": video.create_room_token(room, identity, name, valid_until - now),
    }


def open_room(db: Session, session_id: int, now: datetime | None = None) -> dict:
    """The interviewer's pass for the room, from when Join opens until the
    interview ends."""
    now = now or now_utc()
    session = session_service.get_session(db, session_id)
    state = session_service.join_state(session, now)
    if state == JoinState.TOO_EARLY:
        minutes = get_settings().join_opens_minutes_before
        raise ConflictError(NOT_OPEN_YET.format(minutes=minutes))
    if state != JoinState.OPEN:
        raise ConflictError(FINISHED)
    if session.interviewer_joined_at is None:
        session.interviewer_joined_at = now
        db.commit()
    log_event(logger, "interview_room_opened", session_id=session.id)
    return _room_pass(session, INTERVIEWER, "Interviewer", now)


def admit(db: Session, session_id: int, now: datetime | None = None) -> InterviewSession:
    """Let the waiting candidate in. This starts the interview."""
    now = now or now_utc()
    session = session_service.get_session(db, session_id)
    if session.status != SessionStatus.SCHEDULED:
        raise ConflictError(FINISHED)
    if not session.candidate_waiting:
        raise ConflictError(NOT_WAITING)
    session.status = SessionStatus.IN_PROGRESS
    session.started_at = now
    session.candidate_seen_at = None
    db.commit()
    log_event(logger, "interview_started", session_id=session.id)
    return session


def end(db: Session, session_id: int, now: datetime | None = None) -> InterviewSession:
    """End a started interview for both people and close its room."""
    session = session_service.get_session(db, session_id)
    if session.status != SessionStatus.IN_PROGRESS:
        raise ConflictError(NOT_STARTED)
    session.status = SessionStatus.COMPLETED
    session.ended_at = now or now_utc()
    db.commit()
    video.close_room(video.room_name(session.id))
    log_event(logger, "interview_ended", session_id=session.id)
    return session


def candidate_pass(db: Session, session: InterviewSession, now: datetime | None = None) -> dict:
    """The candidate's pass for the room, only once they were admitted."""
    if session.status != SessionStatus.IN_PROGRESS:
        raise ConflictError(NOT_STARTED)
    name = session.candidate.full_name.split()
    return _room_pass(session, CANDIDATE, name[0] if name else "Candidate", now or now_utc())
