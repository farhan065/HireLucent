from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import CandidateStatus

if TYPE_CHECKING:
    from app.models.assessment import Assessment
    from app.models.interview import InterviewSession
    from app.models.job import Job


class Candidate(TimestampMixin, Base):
    __tablename__ = "candidates"
    # One application per email address per job (duplicate skip at intake).
    __table_args__ = (UniqueConstraint("job_id", "email"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), index=True
    )
    full_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(30))
    # The ID of the form response this application came from, so a later
    # fetch does not collect it again.
    source_ref: Mapped[str | None] = mapped_column(String(100))
    cv_path: Mapped[str] = mapped_column(String(500))
    # The text read from the CV, and how it was read: "text" or "ocr".
    cv_text: Mapped[str | None] = mapped_column(Text)
    cv_text_source: Mapped[str | None] = mapped_column(String(10))
    cv_parsed: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # Why screening could not process this CV, shown to the interviewer.
    screening_error: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), default=CandidateStatus.APPLIED)

    # Final human decision (step 13).
    decision: Mapped[str | None] = mapped_column(String(30))
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)

    job: Mapped["Job"] = relationship(back_populates="candidates")  
    screening_result: Mapped["ScreeningResult | None"] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", passive_deletes=True
    )
    sessions: Mapped[list["InterviewSession"]] = relationship(  
        back_populates="candidate", cascade="all, delete-orphan", passive_deletes=True
    )
    assessments: Mapped[list["Assessment"]] = relationship(  
        back_populates="candidate", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def excluded_reason(self) -> str | None:
        """Why screening excluded the candidate, one reason per line."""
        return self.screening_result.excluded_reason if self.screening_result else None

    @property
    def must_haves_met(self) -> bool | None:
        """Whether the must-have check passed. None until it has run."""
        if self.screening_result is None:
            return None
        return self.screening_result.excluded_reason is None


class ScreeningResult(TimestampMixin, Base):
    __tablename__ = "screening_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), unique=True
    )
    # Per requirement: met / partly met / not met, with CV evidence.
    requirement_matches: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    # Per dimension: score, weight and justification.
    dimension_scores: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    criteria_score: Mapped[float | None] = mapped_column(Float)
    ats_score: Mapped[float | None] = mapped_column(Float)
    final_score: Mapped[float | None] = mapped_column(Float)
    justification: Mapped[str | None] = mapped_column(Text)
    excluded_reason: Mapped[str | None] = mapped_column(Text)

    candidate: Mapped[Candidate] = relationship(back_populates="screening_result")