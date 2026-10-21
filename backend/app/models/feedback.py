"""The feedback email a candidate gets after the decision (innovation
feature F11, Candidate Feedback Composer)."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import FeedbackStatus

if TYPE_CHECKING:
    from app.models.candidate import Candidate
    from app.models.user import User


class CandidateFeedback(TimestampMixin, Base):
    """One email per candidate: the draft while it waits for the
    interviewer, then the text exactly as sent. Deleted with the candidate
    or the job. The candidate's email address is not copied here."""

    __tablename__ = "candidate_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), unique=True
    )
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    # screening_reject, interview_reject, hire or cv_unreadable.
    kind: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default=FeedbackStatus.WAITING_REVIEW)
    # "ai" for an AI draft, "template" for a fixed message.
    written_by: Mapped[str] = mapped_column(String(20))
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    # What each point is based on, for the interviewer only: requirement or
    # report point ids with a short label. Never sent to the candidate.
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    # Fairness warnings still on the draft, each with a code, a message and
    # the words it is about.
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    # Why the last send failed, safe to show.
    error_message: Mapped[str | None] = mapped_column(String(255))
    # True when the interviewer sent it with warnings still on it.
    sent_anyway: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    candidate: Mapped["Candidate"] = relationship(back_populates="feedback")
    approver: Mapped["User | None"] = relationship(viewonly=True)

    @property
    def approved_by_name(self) -> str | None:
        return self.approver.full_name if self.approver else None
