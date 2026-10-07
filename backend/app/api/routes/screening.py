"""CV screening endpoints."""

from fastapi import APIRouter, BackgroundTasks, Depends, status
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.orm import Session

from app.api.deps import Principal, require_interviewer
from app.db.session import get_db
from app.graphs.screening.graph import get_screening_graph
from app.models import Task
from app.schemas.error import ErrorResponse
from app.schemas.task import TaskResponse
from app.services import screening_service

router = APIRouter(prefix="/jobs/{job_id}", tags=["CV screening"])


@router.post(
    "/screen",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Screen the job's CVs that have not been screened yet",
    responses={
        404: {"model": ErrorResponse, "description": "Job not found"},
        409: {"model": ErrorResponse, "description": "There are no CVs to screen"},
    },
)
def start_screening(
    job_id: int,
    background_tasks: BackgroundTasks,
    principal: Principal = Depends(require_interviewer),
    db: Session = Depends(get_db),
    graph: CompiledStateGraph = Depends(get_screening_graph),
) -> Task:
    """Starts in the background and returns a task. Follow its progress with
    GET /tasks/{id}. A CV that cannot be processed is marked as failed with
    the reason, and the others continue."""
    return screening_service.start_screening(
        db, background_tasks, graph, job_id, principal.subject_id
    )
