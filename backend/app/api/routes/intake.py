"""CV intake endpoints: fetching a job's applications and listing candidates."""

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import Principal, require_interviewer
from app.db.session import get_db
from app.models import Candidate, Task
from app.schemas.candidate import CandidateSummary, IntakeStatus
from app.schemas.error import ErrorResponse
from app.schemas.task import TaskResponse
from app.services import intake_service

router = APIRouter(prefix="/jobs/{job_id}", tags=["CV intake"])

NOT_FOUND = {404: {"model": ErrorResponse, "description": "Job not found"}}


@router.post(
    "/intake",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Fetch the CVs submitted through the job's application form",
    responses={
        **NOT_FOUND,
        409: {"model": ErrorResponse, "description": "The job is not published"},
    },
)
def start_intake(
    job_id: int,
    background_tasks: BackgroundTasks,
    principal: Principal = Depends(require_interviewer),
    db: Session = Depends(get_db),
) -> Task:
    """Starts in the background and returns a task. Follow its progress with
    GET /tasks/{id}. Only applications not collected before are added."""
    return intake_service.start_intake(db, background_tasks, job_id, principal.subject_id)


@router.get(
    "/intake/status",
    response_model=IntakeStatus,
    summary="Count the applications waiting to be fetched",
    dependencies=[Depends(require_interviewer)],
    responses=NOT_FOUND,
)
def read_intake_status(job_id: int, db: Session = Depends(get_db)) -> IntakeStatus:
    """Only counts. Nothing is downloaded and no candidate is created."""
    return IntakeStatus(waiting=intake_service.waiting_count(db, job_id))


@router.get(
    "/candidates",
    response_model=list[CandidateSummary],
    summary="List a job's candidates",
    dependencies=[Depends(require_interviewer)],
    responses=NOT_FOUND,
)
def list_candidates(job_id: int, db: Session = Depends(get_db)) -> list[Candidate]:
    return intake_service.list_candidates(db, job_id)
