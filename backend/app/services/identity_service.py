"""IdentityService: checks who joined an interview (F7).

When the candidate joins, one photo is taken in the browser. It is
compared with the invited candidate's application photo (verification)
and with the other applicants of the same job (identification), then
thrown away. Only the result is kept, for the interviewer:

    verified (0.50 or more) · low (0.363 to 0.50) · very low (below 0.363)
    other applicant (another applicant of the job matches better, 0.50 or more)
    not checked (with the reason)

The check never stops anyone from joining, and the candidate never sees
the result. Logs hold the interview id, the result and the score only.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from app.models import Candidate, InterviewSession
from app.models.enums import FaceStatus, IdentityResult, SessionStatus
from app.services import face_service

logger = get_logger(__name__)

# How many unusable photos a candidate may send before they join unchecked.
MAX_PHOTO_TRIES = 3

DONE = "done"
RETRY = "retry"
# No usable photo after the last try: the candidate joins without the check.
GAVE_UP_STATE = "skipped"

NO_CAMERA = "no_camera"
GAVE_UP = "gave_up"
SKIP_REASONS = {
    NO_CAMERA: "The candidate had no working camera when joining.",
    GAVE_UP: "No clear photo could be taken when joining.",
}


def needs_photo(session: InterviewSession) -> bool:
    """Whether the candidate still has to take the identity photo."""
    return (
        session.pin_hash is not None
        and not (session.identity_check or {}).get("result")
        and session.status in (SessionStatus.SCHEDULED, SessionStatus.IN_PROGRESS)
    )


def _no_code_reason(candidate: Candidate) -> str:
    """Why the invited candidate's photo cannot be compared."""
    if candidate.face_status == FaceStatus.NO_CONSENT:
        return "The application has no consent for the photo check."
    if candidate.face_status == FaceStatus.PHOTO_UNUSABLE:
        problem = face_service.PROBLEMS.get(candidate.face_problem or "", "not usable")
        return f"The application photo is not usable ({problem})."
    return "The application has no photo."


def decide(invited_score: float | None, other: tuple[int, float] | None) -> dict[str, Any]:
    """The result from the scores: the invited candidate's, and the best of
    the other applicants of the job (their id and score)."""
    other_matches = other is not None and other[1] >= face_service.VERIFIED
    if other_matches and (invited_score is None or other[1] > invited_score):
        result = {
            "result": IdentityResult.OTHER_APPLICANT,
            "other_candidate_id": other[0],
            "other_score": round(other[1], 2),
        }
        if invited_score is not None:
            result["score"] = round(invited_score, 2)
        return result
    if invited_score is None:
        return {"result": IdentityResult.NOT_CHECKED}
    return {"result": face_service.band(invited_score), "score": round(invited_score, 2)}


def _compare(db: Session, session: InterviewSession, code: bytes) -> dict[str, Any]:
    invited = session.candidate
    invited_score = face_service.similarity(code, invited.face_code) if invited.face_code else None
    others = db.scalars(
        select(Candidate).where(
            Candidate.job_id == session.job_id,
            Candidate.id != invited.id,
            Candidate.face_code.is_not(None),
        )
    )
    best = max(
        ((other.id, face_service.similarity(code, other.face_code)) for other in others),
        key=lambda item: item[1],
        default=None,
    )
    result = decide(invited_score, best)
    if result["result"] == IdentityResult.NOT_CHECKED:
        result["reason"] = _no_code_reason(invited)
    return result


def _save(db: Session, session: InterviewSession, check: dict[str, Any], now: datetime) -> None:
    session.identity_check = {**check, "checked_at": now.isoformat()}
    db.commit()
    log_event(
        logger,
        "identity_checked",
        session_id=session.id,
        result=str(check.get("result")),
        score=check.get("score"),
    )


def check_photo(
    db: Session, session: InterviewSession, content: bytes, now: datetime
) -> tuple[str, int | None]:
    """Check the photo taken when joining. Returns done, retry with the
    tries left when the photo cannot be used, or skipped after the last
    try. The photo is not kept."""
    if not needs_photo(session):
        return DONE, None
    attempts = (session.identity_check or {}).get("attempts", 0) + 1
    face = face_service.check_photo(content)
    if face.problem:
        if attempts >= MAX_PHOTO_TRIES:
            _save(
                db,
                session,
                {
                    "result": IdentityResult.NOT_CHECKED,
                    "reason": SKIP_REASONS[GAVE_UP],
                    "attempts": attempts,
                },
                now,
            )
            return GAVE_UP_STATE, None
        session.identity_check = {"attempts": attempts}
        db.commit()
        log_event(logger, "identity_photo_unusable", session_id=session.id, problem=face.problem)
        return RETRY, MAX_PHOTO_TRIES - attempts
    _save(db, session, {**_compare(db, session, face.code), "attempts": attempts}, now)
    return DONE, None


def skip(db: Session, session: InterviewSession, reason: str, now: datetime) -> None:
    """The candidate continues without a photo (no camera, or gave up)."""
    if not needs_photo(session):
        return
    attempts = (session.identity_check or {}).get("attempts", 0)
    _save(
        db,
        session,
        {
            "result": IdentityResult.NOT_CHECKED,
            "reason": SKIP_REASONS[reason],
            "attempts": attempts,
        },
        now,
    )
