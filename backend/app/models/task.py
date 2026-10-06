"""Background tasks: long-running operations and their progress."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import TaskStatus


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"

    # A random ID, so one user cannot guess another task's address.
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    # What the task does, for example "cv_intake" or "cv_screening".
    kind: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(30), default=TaskStatus.PENDING)
    progress_current: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, default=0)
    # Short text for the user, for example "Reading CV 3 of 20".
    message: Mapped[str | None] = mapped_column(String(255))
    # Summary produced when the task succeeds, for example counts.
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(String(255))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))