"""Job profile endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_interviewer
from app.db.session import get_db
from app.models import Job
from app.schemas.error import ErrorResponse
from app.schemas.job import JobDetail, JobProfileUpdate, JobSummary
from app.services import job_service

router = APIRouter(
    prefix="/jobs", tags=["Jobs"], dependencies=[Depends(require_interviewer)]
)

NOT_FOUND = {404: {"model": ErrorResponse, "description": "Job not found"}}


@router.get("", response_model=list[JobSummary], summary="List all jobs")
def list_jobs(db: Session = Depends(get_db)) -> list[Job]:
    """Jobs, newest first, with the number of candidates in each status."""
    return job_service.list_jobs(db)


@router.get(
    "/{job_id}", response_model=JobDetail, summary="Get one job", responses=NOT_FOUND
)
def read_job(job_id: int, db: Session = Depends(get_db)) -> Job:
    return job_service.get_job(db, job_id)


@router.put(
    "/{job_id}/profile",
    response_model=JobDetail,
    summary="Change a job's requirements and scoring weights",
    responses={
        **NOT_FOUND,
        409: {"model": ErrorResponse, "description": "Screening has started"},
    },
)
def update_job_profile(
    job_id: int, payload: JobProfileUpdate, db: Session = Depends(get_db)
) -> Job:
    """Allowed until the first CV of this job has been screened."""
    return job_service.update_profile(
        db, job_id, payload.requirements, payload.scoring_weights
    )


@router.post(
    "/{job_id}/archive",
    response_model=JobDetail,
    summary="Archive a job",
    responses=NOT_FOUND,
)
def archive_job(job_id: int, db: Session = Depends(get_db)) -> Job:
    return job_service.archive_job(db, job_id)