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
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.logging import get_logger, log_event
from app.db.session import SessionLocal
from app.models import Task
from app.models.enums import TaskStatus

logger = get_logger(__name__)

GENERIC_FAILURE_MESSAGE = "The operation could not be completed. Please try again."
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
) -> Task:
    """Create a task row and schedule its work to run after the response."""
    task = Task(id=uuid4().hex, kind=kind, created_by=created_by)
    db.add(task)
    db.commit()
    background_tasks.add_task(run_task, task.id, work)
    log_event(logger, "task_created", task_id=task.id, kind=kind)
    return task


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
            .where(Task.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING]))
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