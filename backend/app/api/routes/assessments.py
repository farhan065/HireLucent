"""Post-interview assessment endpoints: evaluating interviews and reading
the result. Interviewers only."""

from fastapi import APIRouter, BackgroundTasks, Depends, status
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.orm import Session

from app.api.deps import Principal, require_interviewer
from app.db.session import get_db
from app.graphs.qa_analysis.graph import get_qa_analysis_graph
from app.models import Assessment, Task
from app.schemas.assessment import AssessmentOut
from app.schemas.error import ErrorResponse
from app.schemas.task import TaskResponse
from app.services import evaluation_service

job_router = APIRouter(
    prefix="/jobs/{job_id}", tags=["Assessments"], dependencies=[Depends(require_interviewer)]
)
session_router = APIRouter(
    prefix="/interviews", tags=["Assessments"], dependencies=[Depends(require_interviewer)]
)


@session_router.post(
    "/{session_id}/evaluate",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Evaluate one completed interview",
    responses={
        404: {"model": ErrorResponse, "description": "Interview not found"},
        409: {
            "model": ErrorResponse,
            "description": "Not completed, no transcript, or an evaluation is running",
        },
    },
)
def evaluate_interview(
    session_id: int,
    background_tasks: BackgroundTasks,
    principal: Principal = Depends(require_interviewer),
    db: Session = Depends(get_db),
    graph: CompiledStateGraph = Depends(get_qa_analysis_graph),
) -> Task:
    """Starts in the background and returns a task; follow it with
    GET /tasks/{id}. An interview evaluated before is evaluated again and its
    earlier assessment is replaced."""
    return evaluation_service.start_evaluation(
        db, background_tasks, graph, session_id, principal.subject_id
    )


@job_router.post(
    "/evaluate",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Evaluate the job's completed interviews not evaluated yet",
    responses={
        404: {"model": ErrorResponse, "description": "Job not found"},
        409: {
            "model": ErrorResponse,
            "description": "Nothing new to evaluate, or an evaluation is running",
        },
    },
)
def evaluate_job_interviews(
    job_id: int,
    background_tasks: BackgroundTasks,
    principal: Principal = Depends(require_interviewer),
    db: Session = Depends(get_db),
    graph: CompiledStateGraph = Depends(get_qa_analysis_graph),
) -> Task:
    """Evaluates the interviews one after another in one background task.
    Interviews that already have an assessment are skipped."""
    return evaluation_service.start_job_evaluation(
        db, background_tasks, graph, job_id, principal.subject_id
    )


@session_router.get(
    "/{session_id}/assessment",
    response_model=AssessmentOut,
    summary="Read the interview's assessment",
    responses={404: {"model": ErrorResponse, "description": "Not found or not evaluated"}},
)
def read_assessment(session_id: int, db: Session = Depends(get_db)) -> Assessment:
    """The question-answer pairs found in the transcript, each pointing to its
    transcript turns. Small talk is kept but marked, and is not evaluated."""
    return evaluation_service.get_assessment(db, session_id)
