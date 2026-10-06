"""Chat conversations with the Hiring Assistant, one per job.

The messages themselves are stored by LangGraph in its checkpoints. This
table holds a short summary of each conversation, so they can be listed.
"""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import ConversationStage


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"

    # The same ID as the LangGraph thread that holds the messages.
    thread_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    stage: Mapped[str] = mapped_column(
        String(30), default=ConversationStage.DESCRIBING
    )
    # Set once the conversation has saved its job.
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL")
    )
