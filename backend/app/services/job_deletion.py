"""Deletes a job, or one candidate, together with everything stored for it."""

import logging
import shutil
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger, log_event
from app.graphs.checkpointer import get_checkpointer
from app.graphs.feedback import graph as feedback_graph
from app.graphs.final_assessment import graph as final_graph
from app.graphs.interview_quality import graph as quality_graph
from app.graphs.screening import store as screening_store
from app.models import Candidate, Conversation, InterviewSession, RemovedApplication, Task
from app.rag import store as rag_store
from app.services import (
    evaluation_service,
    interview_chat_service,
    job_service,
    screening_service,
    session_service,
    task_service,
)

logger = get_logger(__name__)

HAS_JOB_MESSAGE = "This conversation has a saved job. Delete the job instead."
OPEN_INTERVIEWS = (
    "This job has upcoming interviews. Cancel them on the Interviews tab before "
    "deleting the job."
)
CANDIDATE_OPEN_INTERVIEW = (
    "This candidate has an upcoming interview. Cancel it on the Interviews tab "
    "before deleting the candidate."
)


def delete_job(db: Session, job_id: int) -> None:
    """Remove a job, its candidates, their CV files, photos, face codes and
    screening data, its conversation, its interviews with their transcripts,
    assessments and saved AI work, and its background tasks. This cannot be
    undone.

    The public job post and the application form are outside the
    application and are not touched. A job with an upcoming or running
    interview cannot be deleted: its candidates hold calendar invitations,
    which only cancelling the interviews withdraws.
    """
    job = job_service.get_job(db, job_id)
    task_service.ensure_idle(db, job_id)
    if session_service.has_open_interviews(db, job_id):
        raise ConflictError(OPEN_INTERVIEWS)

    threads = list(
        db.scalars(select(Conversation.thread_id).where(Conversation.job_id == job_id))
    )
    screening_tasks = db.scalars(
        select(Task.id).where(
            Task.job_id == job_id, Task.kind == screening_service.TASK_KIND
        )
    )
    threads += [screening_service.thread_id(task_id) for task_id in screening_tasks]
    interviews = db.scalars(
        select(InterviewSession.id).where(InterviewSession.job_id == job_id)
    )
    threads += _interview_threads(interviews)
    # Feedback emails (F11): their drafts are kept in the graph's state too.
    candidates = db.scalars(select(Candidate.id).where(Candidate.job_id == job_id))
    threads += [feedback_graph.thread_id(candidate_id) for candidate_id in candidates]

    _delete_cv_vectors({"job_id": job_id})
    db.execute(delete(Conversation).where(Conversation.job_id == job_id))
    # Candidates, screening results and tasks go with the job (cascade).
    db.delete(job)
    db.commit()

    shutil.rmtree(Path(get_settings().cv_storage_dir) / str(job_id), ignore_errors=True)
    _delete_threads(threads)
    log_event(logger, "job_deleted", job_id=job_id)


def delete_draft(db: Session, user_id: int, thread_id: str) -> None:
    """Remove a conversation that has not saved a job yet."""
    conversation = db.get(Conversation, thread_id)
    if conversation is None or conversation.user_id != user_id:
        raise NotFoundError("This conversation does not exist.")
    if conversation.job_id is not None:
        raise ConflictError(HAS_JOB_MESSAGE)
    db.delete(conversation)
    db.commit()
    _delete_threads([thread_id])
    log_event(logger, "conversation_deleted")


def delete_candidate(db: Session, candidate_id: int) -> None:
    """Remove a candidate, their CV file, their application photo and face
    code, their screening results, their CV sections and their interviews
    with the transcripts, assessments and saved AI work. This cannot be
    undone.

    Their form response is remembered by its ID only, so Fetch CVs never
    collects the application again. The ranks of the others are updated. A
    candidate with an upcoming or running interview cannot be deleted: they
    hold a calendar invitation and a join link, which only cancelling the
    interview withdraws.
    """
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise NotFoundError("This candidate does not exist.")
    job_id = candidate.job_id
    task_service.ensure_idle(db, job_id)
    if session_service.candidate_has_open_interview(db, candidate_id):
        raise ConflictError(CANDIDATE_OPEN_INTERVIEW)
    interviews = db.scalars(
        select(InterviewSession.id).where(InterviewSession.candidate_id == candidate_id)
    )
    threads = _interview_threads(interviews)
    threads.append(feedback_graph.thread_id(candidate_id))

    _delete_cv_vectors({"candidate_id": candidate_id})
    if candidate.source_ref:
        db.add(RemovedApplication(job_id=job_id, response_id=candidate.source_ref))
    cv_path = Path(candidate.cv_path)
    photo_path = Path(candidate.photo_path) if candidate.photo_path else None
    # The screening result, the face code, the interviews, their transcripts
    # and assessments and the feedback email go with the candidate (cascade).
    db.delete(candidate)
    db.commit()
    cv_path.unlink(missing_ok=True)
    if photo_path:
        photo_path.unlink(missing_ok=True)
    _delete_threads(threads)

    screening_store.rerank(job_id)
    log_event(logger, "candidate_deleted", candidate_id=candidate_id, job_id=job_id)


def _delete_cv_vectors(where: dict) -> None:
    """Remove CV sections from the vector store: a job's or one candidate's."""
    try:
        rag_store.get_collection(rag_store.CV_EMBEDDINGS).delete(where=where)
    except Exception as exc:
        # The database rows still go. The sections are tagged with this job
        # only, so nothing can reach them once the job is gone.
        log_event(
            logger,
            "cv_vectors_not_deleted",
            level=logging.WARNING,
            error_type=type(exc).__name__,
        )


def _interview_threads(session_ids) -> list[str]:
    """The saved LangGraph state of each interview: the room chat, the
    report, the CV claim check, the interview quality check and any Q&A
    analysis runs. They hold transcript text, CV facts and report text, so
    they are deleted with the interview."""
    threads = []
    for session_id in session_ids:
        threads += [
            interview_chat_service.thread_id(session_id),
            final_graph.thread_id(session_id),
            final_graph.claims_thread_id(session_id),
            quality_graph.thread_id(session_id),
        ]
        threads += _evaluation_threads(session_id)
    return threads


def _evaluation_threads(session_id: int) -> list[str]:
    """Q&A analysis runs are named after their task as well as the
    interview, so they are found by name. Runs are deleted when they finish;
    this finds any left by an older version or a backend that stopped
    mid-run."""
    pattern = evaluation_service.thread_id("%", session_id)
    query = (
        "SELECT thread_id FROM checkpoints WHERE thread_id LIKE %(p)s "
        "UNION SELECT thread_id FROM checkpoint_writes WHERE thread_id LIKE %(p)s "
        "UNION SELECT thread_id FROM checkpoint_blobs WHERE thread_id LIKE %(p)s"
    )
    with get_checkpointer().conn.connection() as conn:
        rows = conn.execute(query, {"p": pattern}).fetchall()
    return [row["thread_id"] for row in rows]


def _delete_threads(threads: list[str]) -> None:
    """Remove the saved LangGraph state, which holds the messages."""
    checkpointer = get_checkpointer()
    for thread in threads:
        checkpointer.delete_thread(thread)
