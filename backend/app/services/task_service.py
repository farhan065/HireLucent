"""Runs long operations in the background and records their progress.

How it is used:
    1. An endpoint calls start_task(...) and returns the task at once.
    2. The work function runs after the response is sent. It reports progress
       through the TaskProgress object it receives.
    3. The client asks GET /tasks/{id} until the status is succeeded or failed.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import BackgroundTasks
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError, ConflictError
from app.core.logging import get_logger, log_event
from app.db.session import SessionLocal
from app.models import Task
from app.models.enums import TaskStatus

logger = get_logger(__name__)

GENERIC_FAILURE_MESSAGE = "The operation could not be completed. Please try again."
BUSY_MESSAGE = (
    "A fetch or a screening is already running for this job. Wait for it to finish."
)
ACTIVE = (TaskStatus.PENDING, TaskStatus.RUNNING)
INTERRUPTED_MESSAGE = "The operation was interrupted by a restart. Please start it again."


class TaskProgress:
    """Given to the work function so it can report how far it has got."""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id

    def update(self, current: int, total: int, message: str | None = None) -> None:
        _save(
            self.task_id,
            progress_current=current,
            progress_total=total,
            message=message,
        )


# The work a task does: receives a TaskProgress, may return a result summary.
Work = Callable[[TaskProgress], dict[str, Any] | None]


def start_task(
    db: Session,
    background_tasks: BackgroundTasks,
    kind: str,
    created_by: int,
    work: Work,
    job_id: int | None = None,
) -> Task:
    """Create a task row and schedule its work to run after the response."""
    task = Task(id=uuid4().hex, kind=kind, created_by=created_by, job_id=job_id)
    db.add(task)
    db.commit()
    background_tasks.add_task(run_task, task.id, work)
    log_event(logger, "task_created", task_id=task.id, kind=kind)
    return task


def running_task(db: Session, job_id: int) -> Task | None:
    """The task that is working on a job right now, if there is one."""
    return db.scalar(
        select(Task).where(Task.job_id == job_id, Task.status.in_(ACTIVE)).limit(1)
    )


def ensure_idle(db: Session, job_id: int) -> None:
    """Refuse to start work on a job that already has a task running, so a
    fetch and a screening never change the same candidates at once."""
    if running_task(db, job_id) is not None:
        raise ConflictError(BUSY_MESSAGE)


def last_finished(db: Session, job_id: int, kind: str) -> Task | None:
    """The most recent finished task of one kind for a job."""
    return db.scalar(
        select(Task)
        .where(Task.job_id == job_id, Task.kind == kind, Task.status.not_in(ACTIVE))
        .order_by(Task.created_at.desc())
        .limit(1)
    )


def run_task(task_id: str, work: Work) -> None:
    """Run the work and record whether it succeeded or failed."""
    _save(task_id, status=TaskStatus.RUNNING, started_at=_now())
    try:
        result = work(TaskProgress(task_id))
    except Exception as exc:
        log_event(
            logger,
            "task_failed",
            level=logging.ERROR,
            task_id=task_id,
            error_type=type(exc).__name__,
        )
        _save(
            task_id,
            status=TaskStatus.FAILED,
            error_message=safe_error_message(exc),
            finished_at=_now(),
        )
        return
    _save(task_id, status=TaskStatus.SUCCEEDED, result=result, finished_at=_now())
    log_event(logger, "task_succeeded", task_id=task_id)


def safe_error_message(exc: Exception) -> str:
    """A message that is safe to show: ours if we wrote it, otherwise generic."""
    return exc.message if isinstance(exc, AppError) else GENERIC_FAILURE_MESSAGE


def fail_interrupted_tasks() -> None:
    """At startup, close tasks that a restart left unfinished.

    Background work does not survive a restart, so without this such tasks
    would show as running forever.
    """
    with SessionLocal() as db:
        result = db.execute(
            update(Task)
            .where(Task.status.in_(ACTIVE))
            .values(
                status=TaskStatus.FAILED,
                error_message=INTERRUPTED_MESSAGE,
                finished_at=_now(),
            )
        )
        db.commit()
    if result.rowcount:
        log_event(logger, "tasks_interrupted", count=result.rowcount)


def _save(task_id: str, **values: Any) -> None:
    """Update one task in its own short database session."""
    with SessionLocal() as db:
        db.execute(update(Task).where(Task.id == task_id).values(**values))
        db.commit()


def _now() -> datetime:
    return datetime.now(timezone.utc)