from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import CandidateStatus

if TYPE_CHECKING:
    from app.models.assessment import Assessment
    from app.models.feedback import CandidateFeedback
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

    # Identity (F7). The application photo, kept under a random name next
    # to the CV so the interviewer can compare it with the video, and its
    # face code (SFace, 128 numbers). Both go when the candidate or the
    # job is deleted. face_status says whether a face code could be made,
    # face_problem why not, face_consent_at when the form's consent was given.
    photo_path: Mapped[str | None] = mapped_column(String(500))
    face_code: Mapped[bytes | None] = mapped_column(LargeBinary)
    face_status: Mapped[str | None] = mapped_column(String(30))
    face_problem: Mapped[str | None] = mapped_column(String(30))
    face_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Final human decision: hire or reject after the interview, set by the
    # interviewer (F11). A candidate rejected at screening gets "reject"
    # when their feedback email is sent.
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
    # The feedback email (F11), once one is written.
    feedback: Mapped["CandidateFeedback | None"] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def feedback_status(self) -> str | None:
        """waiting_review, sending, sent, failed or discarded; empty while
        no email has been written."""
        return self.feedback.status if self.feedback else None

    @property
    def feedback_warnings(self) -> int:
        """How many fairness warnings the email's draft still has."""
        return len(self.feedback.warnings or []) if self.feedback else 0

    @property
    def feedback_sent(self) -> bool:
        """The candidate has been told; their decision and shortlist are
        locked."""
        return self.feedback_status in ("sending", "sent")

    @property
    def has_photo(self) -> bool:
        """Whether an application photo is stored."""
        return bool(self.photo_path)

    @property
    def excluded_reason(self) -> str | None:
        """Why screening excluded the candidate, one reason per line."""
        return self.screening_result.excluded_reason if self.screening_result else None

    @property
    def requirement_matches(self) -> list[dict] | None:
        """Per requirement: met, partially met or unmet, with CV evidence."""
        return self.screening_result.requirement_matches if self.screening_result else None

    @property
    def match_score(self) -> float | None:
        return self.screening_result.match_score if self.screening_result else None

    @property
    def rank(self) -> int | None:
        return self.screening_result.rank if self.screening_result else None

    @property
    def scores(self) -> dict[str, Any] | None:
        """The scores of a screened candidate, with their breakdown."""
        result = self.screening_result
        if result is None or result.final_score is None:
            return None
        return {
            "final_score": result.final_score,
            "criteria_score": result.criteria_score,
            "ats_score": result.ats_score,
            "dimensions": result.dimension_scores,
            "ats": result.ats_details,
            "summary": result.justification,
            "final_rank": result.final_rank,
        }

    @property
    def cv_facts(self) -> dict[str, Any] | None:
        """What was read from the CV, for showing to the interviewer. Email
        addresses and phone numbers are left out: the form's email is shown
        already, and phone numbers are not needed for screening."""
        if not self.cv_parsed:
            return None
        facts = {key: value for key, value in self.cv_parsed.items() if key != "contact"}
        facts["links"] = (self.cv_parsed.get("contact") or {}).get("links", [])
        return facts

    @property
    def match_counts(self) -> dict[str, int] | None:
        """How many requirements are met, partly met and unmet."""
        matches = self.screening_result.requirement_matches if self.screening_result else None
        if matches is None:
            return None
        statuses = [item["status"] for item in matches]
        return {key: statuses.count(key) for key in ("met", "partially_met", "unmet")}

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
    # How well the CV matches the requirements (0 to 100), and the rank it
    # gives among the job's candidates. The final score replaces this ranking
    # once scoring exists.
    match_score: Mapped[float | None] = mapped_column(Float)
    rank: Mapped[int | None] = mapped_column(Integer)
    # The rank by final score among the job's scored candidates.
    final_rank: Mapped[int | None] = mapped_column(Integer)
    criteria_score: Mapped[float | None] = mapped_column(Float)
    ats_score: Mapped[float | None] = mapped_column(Float)
    # The two parts of the ATS score: keyword coverage and similarity.
    ats_details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    final_score: Mapped[float | None] = mapped_column(Float)
    justification: Mapped[str | None] = mapped_column(Text)
    excluded_reason: Mapped[str | None] = mapped_column(Text)

    candidate: Mapped[Candidate] = relationship(back_populates="screening_result")


class RemovedApplication(TimestampMixin, Base):
    """A form response whose candidate the interviewer deleted. Fetch CVs
    skips it, so a deleted application is never collected again. Only
    Google's response ID is kept, which holds no personal data."""

    __tablename__ = "removed_applications"
    __table_args__ = (UniqueConstraint("job_id", "response_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    response_id: Mapped[str] = mapped_column(String(100))
