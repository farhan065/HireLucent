"""Candidate endpoints."""

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import require_interviewer
from app.db.session import get_db
from app.schemas.error import ErrorResponse
from app.services import intake_service

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
