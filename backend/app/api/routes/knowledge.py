"""Knowledge Base endpoints."""

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import Principal, require_interviewer
from app.db.session import get_db
from app.models import Document
from app.schemas.error import ErrorResponse
from app.schemas.knowledge import DocumentKind, DocumentResponse
from app.services import knowledge_service

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"])


@router.post(
    "/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a document to the Knowledge Base",
    responses={
        413: {"model": ErrorResponse, "description": "File too large"},
        415: {"model": ErrorResponse, "description": "File type not supported"},
    },
)
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(description="A PDF, DOCX, TXT or Markdown file."),
    doc_type: DocumentKind = Form(description="What the document is used for."),
    tags: str = Form(default="", max_length=500, description="Tags separated by commas."),
    principal: Principal = Depends(require_interviewer),
    db: Session = Depends(get_db),
) -> Document:
    """The upload is accepted at once and processed in the background.
    Its status changes from processing to ready or failed."""
    return knowledge_service.upload_document(
        db,
        background_tasks,
        filename=file.filename or "document",
        content=file.file.read(),
        doc_type=doc_type,
        tags=[tag.strip() for tag in tags.split(",") if tag.strip()],
        uploaded_by=principal.subject_id,
    )


@router.get(
    "/documents",
    response_model=list[DocumentResponse],
    summary="List Knowledge Base documents",
    dependencies=[Depends(require_interviewer)],
)
def list_documents(db: Session = Depends(get_db)) -> list[Document]:
    return knowledge_service.list_documents(db)


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document and its stored text",
    dependencies=[Depends(require_interviewer)],
    responses={404: {"model": ErrorResponse, "description": "Document not found"}},
)
def delete_document(document_id: int, db: Session = Depends(get_db)) -> None:
    knowledge_service.delete_document(db, document_id)
