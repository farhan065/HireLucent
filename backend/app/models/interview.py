from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, object_session, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import IdentityResult, SessionStatus

if TYPE_CHECKING:
    from app.models.assessment import Assessment
    from app.models.candidate import Candidate

NOT_TAKEN = "No photo was taken before the interview started."

# The candidate's waiting page checks in every few seconds. Without a check
# for this long, they are no longer counted as waiting.
WAITING_TIMEOUT = timedelta(seconds=15)


class InterviewSession(TimestampMixin, Base):
    __tablename__ = "interview_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), index=True
    )
    # The interviewer who scheduled it. Two interviews of the same
    # interviewer may not overlap.
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    scheduled_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Only the hash of the private join token is stored, never the token.
    join_token_hash: Mapped[str] = mapped_column(String(255), unique=True)
    calendar_event_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), default=SessionStatus.SCHEDULED)
    candidate_joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    interviewer_joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_given_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # When the candidate's waiting page last checked in.
    candidate_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Questions the AI suggested for this candidate, with whether each was
    # asked. Kept for the interview room and the assessment after it.
    suggested_questions: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    # The interview PIN (F7): only its Argon2 hash is stored. Five wrong
    # tries lock the link for a while. Interviews scheduled before F7 have
    # no PIN and no identity check.
    pin_hash: Mapped[str | None] = mapped_column(String(255))
    pin_failed_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    pin_locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The identity check when the candidate joined: result, match scores,
    # another applicant it matched, the reason when not checked, the time
    # and the number of photos tried. Never the photo itself.
    identity_check: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    candidate: Mapped["Candidate"] = relationship(  
        back_populates="sessions"
    )
    # The interview's assessment, once it has been evaluated.
    assessment: Mapped["Assessment | None"] = relationship(viewonly=True, uselist=False)
    turns: Mapped[list["TranscriptTurn"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TranscriptTurn.start_ms",
    )

    @property
    def candidate_name(self) -> str:
        """The candidate's name, for the interviewer's list of interviews."""
        return self.candidate.full_name

    @property
    def assessment_status(self) -> str | None:
        """analysed, draft or approved; None until the interview is evaluated."""
        return self.assessment.status if self.assessment else None

    @property
    def identity(self) -> dict[str, Any] | None:
        """The identity check for the interviewer (F7): pending until the
        candidate has taken the photo. None for interviews scheduled before
        F7, which have no PIN."""
        if self.pin_hash is None:
            return None
        check = dict(self.identity_check or {})
        if not check.get("result"):
            if self.status == SessionStatus.SCHEDULED:
                return {"result": IdentityResult.PENDING}
            return {"result": IdentityResult.NOT_CHECKED, "reason": NOT_TAKEN}
        other_id = check.pop("other_candidate_id", None)
        if other_id:
            from app.models.candidate import Candidate

            db = object_session(self)
            other = db.get(Candidate, other_id) if db else None
            check["other_candidate_name"] = other.full_name if other else None
        check.pop("attempts", None)
        return check

    @property
    def candidate_waiting(self) -> bool:
        """True while the candidate is in the waiting room of an interview
        that has not started."""
        if self.status != SessionStatus.SCHEDULED or self.candidate_seen_at is None:
            return False
        return datetime.now(timezone.utc) - self.candidate_seen_at <= WAITING_TIMEOUT


class TranscriptTurn(Base):
    __tablename__ = "transcript_turns"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True
    )
    speaker: Mapped[str] = mapped_column(String(30))
    # Milliseconds from the start of the interview.
    start_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)

    session: Mapped[InterviewSession] = relationship(back_populates="turns")