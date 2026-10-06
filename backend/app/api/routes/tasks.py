"""Background task endpoints."""

import time

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import Principal, require_interviewer
from app.core.errors import NotFoundError
from app.db.session import get_db
from app.models import Task
from app.schemas.task import DemoTaskRequest, TaskResponse
from app.services import task_service
from app.services.task_service import TaskProgress

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post(
    "/demo",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a demo task that counts through a number of steps",
)
def start_demo_task(
    payload: DemoTaskRequest,
    background_tasks: BackgroundTasks,
    principal: Principal = Depends(require_interviewer),
    db: Session = Depends(get_db),
) -> Task:
    """Start a slow task and return at once. Used to try the framework."""

    def work(progress: TaskProgress) -> dict:
        for step in range(1, payload.steps + 1):
            if step == payload.fail_at:
                raise RuntimeError("demo failure")
            time.sleep(2)
            progress.update(step, payload.steps, f"Step {step} of {payload.steps}")
        return {"steps_completed": payload.steps}

    return task_service.start_task(
        db, background_tasks, "demo", principal.subject_id, work
    )


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get the status and progress of a task",
    dependencies=[Depends(require_interviewer)],
)
def read_task(task_id: str, db: Session = Depends(get_db)) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise NotFoundError("This task does not exist.")
    return task