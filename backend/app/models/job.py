"""Job profiles: the approved job description, requirements and weights."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import JobStatus

if TYPE_CHECKING:
    from app.models.candidate import Candidate


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_code: Mapped[str] = mapped_column(String(30), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    jd_text: Mapped[str] = mapped_column(Text)
    # Must-haves, preferred skills, minimum experience and qualifications.
    requirements: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # Decided once per job so every CV is scored the same way.
    scoring_weights: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30), default=JobStatus.APPROVED)
    # The Google Form candidates apply through: its ID, used to read the
    # responses, and the public address shown in the job post.
    form_id: Mapped[str | None] = mapped_column(String(100))
    form_url: Mapped[str | None] = mapped_column(String(500))
    # How many form responses the last fetch saw. A higher number on the
    # form now means new applications are waiting.
    responses_seen: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    post_url: Mapped[str | None] = mapped_column(String(500))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))

    candidates: Mapped[list["Candidate"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", passive_deletes=True
    )