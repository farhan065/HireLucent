from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import AssessmentStatus

if TYPE_CHECKING:
    from app.models.candidate import Candidate



class Assessment(TimestampMixin, Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    # Unique: evaluating a session again updates its existing row.
    session_id: Mapped[int] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), unique=True
    )
    status: Mapped[str] = mapped_column(String(30), default=AssessmentStatus.ANALYSED)

    # Written by the Q&A Analysis graph.
    qa_evaluations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    coverage_map: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)

    # Written by the Final Assessment graph, so empty until then.
    cv_score: Mapped[float | None] = mapped_column(Float)
    interview_score: Mapped[float | None] = mapped_column(Float)
    overall_score: Mapped[float | None] = mapped_column(Float)
    strengths: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    weaknesses: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    gaps: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    areas_to_verify: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    report: Mapped[str | None] = mapped_column(Text)

    # Human review of the report.
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    candidate: Mapped["Candidate"] = relationship(  # noqa: F821
        back_populates="assessments"
    )