"""Candidate endpoints."""

from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import require_interviewer
from app.db.session import get_db
from app.models import Candidate
from app.schemas.candidate import CandidateSummary, ShortlistChange
from app.schemas.error import ErrorResponse
from app.services import intake_service, job_deletion, shortlist_service

router = APIRouter(
    prefix="/candidates", tags=["Candidates"], dependencies=[Depends(require_interviewer)]
)

MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.get(
    "/{candidate_id}/cv",
    response_class=FileResponse,
    summary="Open the CV a candidate uploaded",
    responses={404: {"model": ErrorResponse, "description": "Candidate or file not found"}},
)
def read_cv_file(candidate_id: int, db: Session = Depends(get_db)) -> FileResponse:
    """For signed-in interviewers only. The file is sent under a neutral
    name, so the address and the download hold no personal data."""
    path = intake_service.cv_file(db, candidate_id)
    return FileResponse(
        path,
        media_type=MEDIA_TYPES.get(path.suffix, "application/octet-stream"),
        filename=f"cv{path.suffix}",
        content_disposition_type="inline",
    )


NOT_FOUND = {404: {"model": ErrorResponse, "description": "Candidate not found"}}


@router.put(
    "/{candidate_id}/shortlist",
    response_model=CandidateSummary,
    summary="Add a candidate to the shortlist, or remove them from it",
    responses={**NOT_FOUND, 409: {"model": ErrorResponse, "description": "Not scored yet"}},
)
def change_shortlist(
    candidate_id: int, payload: ShortlistChange, db: Session = Depends(get_db)
) -> Candidate:
    """Only candidates with a final score can be shortlisted. The rank and
    scores do not change."""
    return shortlist_service.set_shortlisted(db, candidate_id, payload.shortlisted)


@router.delete(
    "/{candidate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a candidate and everything stored for them",
    responses={**NOT_FOUND, 409: {"model": ErrorResponse, "description": "A task is running"}},
)
def delete_candidate(candidate_id: int, db: Session = Depends(get_db)) -> None:
    """Removes the candidate, their CV file, their screening results and
    their CV sections. Their application is never collected again. This
    cannot be undone."""
    job_deletion.delete_candidate(db, candidate_id)
