"""Keeps the short summary of each conversation in the database."""

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import Conversation, Job
from app.schemas.chat import ConversationView


def save_summary(user_id: int, view: ConversationView) -> None:
    """Create or update the summary row after a turn."""
    with SessionLocal() as db:
        conversation = db.get(Conversation, view.thread_id)
        if conversation is None:
            conversation = Conversation(thread_id=view.thread_id, user_id=user_id)
            db.add(conversation)
        conversation.title = view.title[:255]
        conversation.stage = view.stage
        conversation.job_id = view.brief.job_id
        # Set explicitly so the list is ordered by last use even when the
        # title and stage did not change.
        conversation.updated_at = func.now()
        db.commit()


def list_summaries(user_id: int) -> list[Conversation]:
    """The interviewer's conversations, most recently used first."""
    with SessionLocal() as db:
        return list(
            db.scalars(
                select(Conversation)
                .where(Conversation.user_id == user_id)
                .order_by(Conversation.updated_at.desc())
            )
        )


def job_code_for(job_id: int | None) -> str | None:
    """The job code of a saved job, for showing in the job brief."""
    if job_id is None:
        return None
    with SessionLocal() as db:
        return db.scalar(select(Job.job_code).where(Job.id == job_id))


def job_profile_for(job_id: int | None) -> tuple[dict, dict] | None:
    """The saved job's current requirements and weights. They can be edited
    after saving, so the job brief shows these rather than the card that
    was approved in the conversation."""
    if job_id is None:
        return None
    with SessionLocal() as db:
        row = db.execute(
            select(Job.requirements, Job.scoring_weights).where(Job.id == job_id)
        ).first()
    return (row.requirements, row.scoring_weights) if row else None
