"""PinService: the 8-digit interview PIN (F7).

The PIN is made when an interview is scheduled and put in the calendar
invitation right under the join link. The candidate types it before
joining, so a leaked link alone is not enough to join. Only its Argon2
hash is stored; the PIN itself exists only in the invitation.

Five wrong tries lock the link for 15 minutes. A new PIN comes with every
reschedule and with "Send a new PIN"; a cancelled interview's PIN stops
working with its link.
"""

import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.logging import get_logger, log_event
from app.core.security import hash_password, verify_password
from app.models import InterviewSession

logger = get_logger(__name__)

PIN_DIGITS = 8
MAX_TRIES = 5
LOCK_TIME = timedelta(minutes=15)
_SPACES = re.compile(r"[\s-]")

OK = "ok"
WRONG = "wrong"
LOCKED = "locked"


@dataclass(frozen=True)
class PinCheck:
    """What a PIN check found: ok, wrong (with the tries left) or locked
    (with the time it unlocks)."""

    result: str
    tries_left: int | None = None
    locked_until: datetime | None = None


def new_pin(session: InterviewSession) -> str:
    """Give the interview a new random PIN and return it, for the
    invitation only. Any earlier PIN and lock stop applying."""
    pin = f"{secrets.randbelow(10**PIN_DIGITS):0{PIN_DIGITS}d}"
    session.pin_hash = hash_password(pin)
    session.pin_failed_attempts = 0
    session.pin_locked_until = None
    return pin


def shown(pin: str) -> str:
    """The PIN as written in the invitation: "4829 1067"."""
    return f"{pin[:4]} {pin[4:]}"


def normalise(pin: str) -> str:
    """The digits the candidate typed, without spaces or dashes."""
    return _SPACES.sub("", pin)


def is_locked(session: InterviewSession, now: datetime) -> bool:
    return session.pin_locked_until is not None and now < session.pin_locked_until


def check(session: InterviewSession, pin: str, now: datetime) -> PinCheck:
    """Check a typed PIN. The caller commits. A correct PIN resets the
    count; the fifth wrong one locks the link."""
    if is_locked(session, now):
        return PinCheck(LOCKED, locked_until=session.pin_locked_until)
    if session.pin_hash and verify_password(normalise(pin), session.pin_hash):
        session.pin_failed_attempts = 0
        session.pin_locked_until = None
        return PinCheck(OK)
    session.pin_failed_attempts = (session.pin_failed_attempts or 0) + 1
    if session.pin_failed_attempts >= MAX_TRIES:
        session.pin_failed_attempts = 0
        session.pin_locked_until = now + LOCK_TIME
        log_event(logger, "interview_pin_locked", session_id=session.id)
        return PinCheck(LOCKED, locked_until=session.pin_locked_until)
    log_event(logger, "interview_pin_wrong", session_id=session.id)
    return PinCheck(WRONG, tries_left=MAX_TRIES - session.pin_failed_attempts)
