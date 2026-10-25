"""Background task endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_interviewer
from app.core.errors import NotFoundError
from app.db.session import get_db
from app.models import Task
from app.schemas.task import TaskResponse

router = APIRouter(prefix="/tasks", tags=["Tasks"])


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
