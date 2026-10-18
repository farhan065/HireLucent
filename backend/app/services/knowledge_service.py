"""KnowledgeService: stores uploaded documents so the AI can refer to them.

An upload is checked and recorded at once, and the slower work (reading the
text, splitting it, embedding it) runs in the background. The document's
status shows how that went: processing, ready or failed.
"""

import logging

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.core.logging import get_logger, log_event
from app.db.session import SessionLocal
from app.models import Document
from app.models.enums import DocumentStatus, DocumentType
from app.rag import store
from app.rag.chunking import chunk_text, split_questions
from app.services.text_extraction import check_file, extract_text

logger = get_logger(__name__)

# Which collection each kind of document is stored in.
COLLECTIONS = {
    DocumentType.JD_TEMPLATE: store.JD_REFERENCES,
    DocumentType.REFERENCE: store.RAG_DOCUMENTS,
    DocumentType.QUESTIONS: store.QUESTION_BANK,
}


def upload_document(
    db: Session,
    background_tasks: BackgroundTasks,
    filename: str,
    content: bytes,
    doc_type: str,
    tags: list[str],
    uploaded_by: int,
) -> Document:
    """Check and record an upload, then process it in the background."""
    extension = check_file(filename, content, get_settings().max_upload_mb)
    document = Document(
        filename=filename[:255],
        doc_type=doc_type,
        tags=tags,
        status=DocumentStatus.PROCESSING,
        uploaded_by=uploaded_by,
    )
    db.add(document)
    db.commit()
    background_tasks.add_task(ingest_document, document.id, extension, content)
    log_event(logger, "document_uploaded", document_id=document.id, doc_type=doc_type)
    return document


def ingest_document(document_id: int, extension: str, content: bytes) -> None:
    """Read, split, embed and store one document. Runs after the response."""
    with SessionLocal() as db:
        document = db.get(Document, document_id)
        if document is None:
            return
        try:
            text = extract_text(extension, content)
            if document.doc_type == DocumentType.QUESTIONS:
                chunks = split_questions(text)
            else:
                chunks = chunk_text(text)
            if not chunks:
                raise ValueError("no readable text")
            store.add_chunks(
                COLLECTIONS[document.doc_type],
                document.id,
                chunks,
                {"source": document.filename, "tags": ", ".join(document.tags)},
            )
        except Exception as exc:
            document.status = DocumentStatus.FAILED
            db.commit()
            log_event(
                logger,
                "document_failed",
                level=logging.ERROR,
                document_id=document_id,
                error_type=type(exc).__name__,
            )
            return
        document.status = DocumentStatus.READY
        document.chunk_count = len(chunks)
        db.commit()
        log_event(
            logger, "document_ready", document_id=document_id, chunk_count=len(chunks)
        )


def interview_questions_name(job_code: str) -> str:
    """The Knowledge Base document that holds a job's questions added from
    its interviews."""
    return f"Interview questions - {job_code}.txt"


def add_interview_questions(
    db: Session, job_code: str, role: str, questions: list[str], added_by: int
) -> Document:
    """Add questions from an interview to the question bank.

    They go into one question bank document per job, created on first use
    and tagged with the job title as its role, so they are suggested in
    later interviews for the same role. The document is listed on the
    Knowledge Base page like an upload, and deleting it removes them.
    Raises ServiceUnavailableError when the embedding model cannot be reached.
    """
    filename = interview_questions_name(job_code)
    document = db.scalar(
        select(Document).where(
            Document.filename == filename, Document.doc_type == DocumentType.QUESTIONS
        )
    )
    if document is None:
        document = Document(
            filename=filename,
            doc_type=DocumentType.QUESTIONS,
            tags=[role],
            status=DocumentStatus.READY,
            chunk_count=0,
            uploaded_by=added_by,
        )
        db.add(document)
        db.flush()
    store.add_chunks(
        store.QUESTION_BANK,
        document.id,
        questions,
        {"source": document.filename, "tags": ", ".join(document.tags)},
        first_index=document.chunk_count,
    )
    document.chunk_count += len(questions)
    db.commit()
    log_event(
        logger, "interview_questions_added", document_id=document.id, count=len(questions)
    )
    return document


def list_documents(db: Session) -> list[Document]:
    return list(db.scalars(select(Document).order_by(Document.created_at.desc())))


def delete_document(db: Session, document_id: int) -> None:
    """Remove a document and everything stored from it."""
    document = db.get(Document, document_id)
    if document is None:
        raise NotFoundError("This document does not exist.")
    store.delete_document(COLLECTIONS[document.doc_type], document.id)
    db.delete(document)
    db.commit()
    log_event(logger, "document_deleted", document_id=document_id)
