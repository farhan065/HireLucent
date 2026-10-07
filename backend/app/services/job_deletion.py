"""Deletes a job together with everything stored for it."""

import shutil
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger, log_event
from app.graphs.checkpointer import get_checkpointer
from app.models import Conversation, Task
from app.services import job_service, screening_service, task_service

logger = get_logger(__name__)

HAS_JOB_MESSAGE = "This conversation has a saved job. Delete the job instead."


def delete_job(db: Session, job_id: int) -> None:
    """Remove a job, its candidates, their CV files and screening data, its
    conversation and its background tasks. This cannot be undone.

    The public job post and the application form are outside the
    application and are not touched.
    """
    job = job_service.get_job(db, job_id)
    task_service.ensure_idle(db, job_id)

    threads = list(
        db.scalars(select(Conversation.thread_id).where(Conversation.job_id == job_id))
    )
    screening_tasks = db.scalars(
        select(Task.id).where(
            Task.job_id == job_id, Task.kind == screening_service.TASK_KIND
        )
    )
    threads += [screening_service.thread_id(task_id) for task_id in screening_tasks]

    db.execute(delete(Conversation).where(Conversation.job_id == job_id))
    # Candidates, screening results and tasks go with the job (cascade).
    db.delete(job)
    db.commit()

    shutil.rmtree(Path(get_settings().cv_storage_dir) / str(job_id), ignore_errors=True)
    _delete_threads(threads)
    log_event(logger, "job_deleted", job_id=job_id)


def delete_draft(db: Session, user_id: int, thread_id: str) -> None:
    """Remove a conversation that has not saved a job yet."""
    conversation = db.get(Conversation, thread_id)
    if conversation is None or conversation.user_id != user_id:
        raise NotFoundError("This conversation does not exist.")
    if conversation.job_id is not None:
        raise ConflictError(HAS_JOB_MESSAGE)
    db.delete(conversation)
    db.commit()
    _delete_threads([thread_id])
    log_event(logger, "conversation_deleted")


def _delete_threads(threads: list[str]) -> None:
    """Remove the saved LangGraph state, which holds the messages."""
    checkpointer = get_checkpointer()
    for thread in threads:
        checkpointer.delete_thread(thread)
